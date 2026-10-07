"""Remediation task creation for blocking findings."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.models import Finding
from core.commands.context import CommandContext
from core.domain.canonical_json import sha256_hex
from core.domain.enums import TaskContractStatus, TaskOrigin, WorkType
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError, Unauthorized
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody, VersionedRef
from core.domain.tasks.service import TaskService
from core.integration.enums import FindingStatus


class RemediationService:
    async def remediate_finding(
        self,
        session: AsyncSession,
        finding_id: uuid.UUID,
        ctx: CommandContext,
    ) -> uuid.UUID:
        if ctx.actor.kind.name == "AGENT":
            raise Unauthorized("Agents cannot create remediation tasks directly")
        finding = await session.get(Finding, finding_id)
        if finding is None:
            raise DomainError(code="NOT_FOUND", message="Finding not found")
        if not finding.blocking:
            raise DomainError(code="INVALID_STATE", message="Finding is not blocking")
        task = await TaskService().create_task(
            session,
            finding.delivery_cycle_id,
            f"Remediate {finding.key}",
            WorkType.CODE_CHANGE,
            TaskOrigin.REMEDIATION,
            ctx,
        )
        allowed_scope: list[str] = []
        for ref in finding.code_refs or []:
            if isinstance(ref, dict) and ref.get("file_path"):
                allowed_scope.append(str(ref["file_path"]))
        if not allowed_scope:
            allowed_scope = ["**"]
        from core.domain.delivery_cycles.models import DeliveryCycle

        cycle = await session.get(DeliveryCycle, finding.delivery_cycle_id)
        repository_id = cycle.repository_id if cycle is not None else None
        base_commit = finding.commit_sha
        if base_commit is None and cycle is not None:
            base_commit = cycle.base_sha
        scope_hint = ", ".join(allowed_scope[:8])
        body = TaskContractBody(
            objective=(
                f"Remediate finding: {finding.title}. "
                f"Fix verification failures using only: {scope_hint}."
            ),
            work_type=WorkType.CODE_CHANGE,
            inputs=[VersionedRef(ref_type="FINDING", ref_id=finding.id)],
            repository_id=repository_id,
            base_policy="EXPLICIT_SHA" if base_commit else "NONE",
            base_commit=base_commit,
            allowed_scope=allowed_scope,
            allowed_actions=[
                "repo.read",
                "repo.search",
                "repo.list",
                "repo.write",
                "shell.run",
                "test.run",
                "git.diff",
                "git.status",
                "git.commit",
                "olympus.submit_artifact",
            ],
            constraints=[f"finding:{finding.key}"],
            executor_kind="AGENT_RUNTIME",
            agent_profile="forge.implementation",
            model_alias="implementation",
            required_outputs=["candidate_commit", "implementation_result"],
        )
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body=body.model_dump(mode="json"),
            content_hash=sha256_hex(f"remediation-{finding.id}"),
            compiled_by="assurance",
        )
        session.add(contract)
        finding.status = FindingStatus.IN_REMEDIATION
        finding.remediation_task_id = task.id
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        await append_domain_event(
            session,
            aggregate_type="finding",
            aggregate_id=finding.id,
            event_type="remediation.requested",
            payload={"task_id": str(task.id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=finding.project_id,
            delivery_cycle_id=finding.delivery_cycle_id,
        )
        return task.id
