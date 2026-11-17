"""Remediation task creation for blocking findings."""

from __future__ import annotations

import json
import uuid
from typing import Literal

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
        from core.domain.delivery_cycles.models import DeliveryCycle

        cycle = await session.get(DeliveryCycle, finding.delivery_cycle_id)
        repository_id = cycle.repository_id if cycle is not None else None
        allowed_scope = await _remediation_scope(session, finding, cycle)
        previous = await _latest_live_remediation(session, finding.delivery_cycle_id, task.id)
        base_policy: Literal["QUEUE_TIP", "DEPENDENCY_INTEGRATION", "EXPLICIT_SHA", "NONE"]
        base_commit: str | None = None
        if previous is not None:
            # Fixes run one after another, in the order they were asked for.
            await TaskService().add_dependency(session, task.id, previous)
        if repository_id is not None and cycle is not None and cycle.base_sha:
            # Merge queue: start from all the code finished so far (the reviewed code and every
            # earlier fix), so fixes build on each other and do not conflict when merged.
            base_policy = "QUEUE_TIP"
        elif previous is not None:
            base_policy = "DEPENDENCY_INTEGRATION"
        else:
            base_commit = finding.commit_sha or (cycle.base_sha if cycle is not None else None)
            base_policy = "EXPLICIT_SHA" if base_commit else "NONE"
        body = TaskContractBody(
            objective=_remediation_objective(finding, allowed_scope),
            work_type=WorkType.CODE_CHANGE,
            inputs=[VersionedRef(ref_type="FINDING", ref_id=finding.id)],
            repository_id=repository_id,
            base_policy=base_policy,
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


def _remediation_objective(finding: Finding, allowed_scope: list[str]) -> str:
    """The agent only sees the contract: give it the reviewer's explanation, not just a title."""
    detail = finding.detail if isinstance(finding.detail, dict) else {}
    explanation = str(detail.get("detail") or detail.get("summary") or "").strip()
    if not explanation and detail:
        explanation = json.dumps(detail)[:2000]
    where = ", ".join(
        f"{r['file_path']}:{r.get('line_start') or ''}".rstrip(":")
        for r in finding.code_refs or []
        if isinstance(r, dict) and r.get("file_path")
    )
    specs = ", ".join(str(s) for s in finding.spec_refs or [])
    parts = [f"Fix finding {finding.key} ({finding.category}): {finding.title}."]
    if explanation:
        parts.append(f"Reviewer's explanation: {explanation}")
    if where:
        parts.append(f"Where: {where}.")
    if specs:
        parts.append(f"Specs it refers to: {specs}.")
    parts.append(
        "Change only what the fix needs, add or update tests that prove it, run the tests, "
        f"then call git.commit. Allowed files: {', '.join(allowed_scope[:12])}."
    )
    return " ".join(parts)


async def _remediation_scope(
    session: AsyncSession, finding: Finding, cycle: object | None
) -> list[str]:
    """Files the fix may touch: the files named in the finding, the file_scope of the approved
    implementation specs it cites, and tests. One file is rarely enough (a missing persistence
    layer spans model, repository and service)."""
    from sqlalchemy import select

    from core.domain.enums import SpecStatus
    from core.planning.models import ImplementationSpec

    scope: list[str] = []

    def add(pattern: str) -> None:
        if pattern and pattern not in scope:
            scope.append(pattern)

    for ref in finding.code_refs or []:
        if isinstance(ref, dict) and ref.get("file_path"):
            add(str(ref["file_path"]))
    project_id = getattr(cycle, "project_id", None)
    spec_keys = [str(s) for s in finding.spec_refs or [] if str(s).startswith("SPEC-IMPL")]
    if project_id is not None and spec_keys:
        rows = await session.execute(
            select(ImplementationSpec).where(
                ImplementationSpec.project_id == project_id,
                ImplementationSpec.lineage_key.in_(spec_keys),
                ImplementationSpec.status == SpecStatus.APPROVED,
            )
        )
        for spec in rows.scalars():
            for pattern in (spec.body or {}).get("file_scope") or []:
                add(str(pattern))
    if any(p.startswith("app/api") for p in scope):
        # Adding or removing a route means touching the app's router wiring.
        add("app/main.py")
    if scope:
        add("tests/**")
    return scope or ["**"]


async def _latest_live_remediation(
    session: AsyncSession, cycle_id: uuid.UUID, exclude: uuid.UUID
) -> uuid.UUID | None:
    from sqlalchemy import select

    from core.domain.enums import TaskStatus
    from core.domain.tasks.models import Task

    row = await session.execute(
        select(Task.id)
        .where(
            Task.delivery_cycle_id == cycle_id,
            Task.origin == TaskOrigin.REMEDIATION,
            Task.work_type == WorkType.CODE_CHANGE,
            Task.id != exclude,
            Task.status.notin_([TaskStatus.CANCELLED, TaskStatus.FAILED]),
            Task.title.startswith("Remediate F"),
        )
        # Fix tasks requested together share a transaction timestamp; the zero-padded task key
        # breaks the tie so each one chains onto the one created just before it.
        .order_by(Task.created_at.desc(), Task.key.desc())
        .limit(1)
    )
    return row.scalar_one_or_none()
