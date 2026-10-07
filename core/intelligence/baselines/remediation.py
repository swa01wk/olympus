"""Brownfield readiness remediation — ImplementationSpec, forge task, IC release."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.approvals.service import ApprovalService
from core.domain.canonical_json import sha256_hex
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import (
    ActorRole,
    ApprovalStatus,
    DeliveryCycleType,
    SpecKind,
    SpecStatus,
    TaskOrigin,
    WorkType,
)
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError, Unauthorized
from core.domain.sequences import next_project_key
from core.domain.task_contracts.schemas import TaskContractBody, VersionedRef
from core.domain.task_contracts.service import ContractService
from core.domain.tasks.service import TaskService
from core.intelligence.baselines.enums import ReadinessResult
from core.intelligence.baselines.models import ReadinessAssessment
from core.intelligence.baselines.orchestrator import BaselineOrchestrator
from core.planning.implementation_specs.service import ImplementationSpecService
from core.planning.models import Architecture, ImplementationSpec
from core.policy.policy_service import ensure_policy_version
from core.product_model.models import FeatureSpec


class BrownfieldRemediationService:
    async def draft_for_cycle(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> ImplementationSpec:
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None or cycle.type != DeliveryCycleType.BROWNFIELD_ONBOARDING:
            raise DomainError(code="INVALID_CYCLE", message="Brownfield cycle required")
        assessment = await self._latest_assessment(session, cycle_id)
        if assessment is None or assessment.result != ReadinessResult.NOT_READY:
            raise DomainError(code="READINESS_NOT_FAILED", message="No NOT_READY assessment")
        if not assessment.remediable:
            raise DomainError(code="NOT_REMEDIABLE", message="Assessment not remediable")
        arch = (
            await session.execute(
                select(Architecture)
                .where(
                    Architecture.project_id == cycle.project_id,
                    Architecture.status == SpecStatus.APPROVED,
                )
                .order_by(Architecture.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if arch is None:
            raise DomainError(code="ARCHITECTURE_MISSING", message="Approved architecture required")
        feature_spec = (
            await session.execute(
                select(FeatureSpec)
                .where(
                    FeatureSpec.project_id == cycle.project_id,
                    FeatureSpec.spec_kind.in_((SpecKind.CANONICAL, SpecKind.RECOVERED)),
                    FeatureSpec.status.in_(
                        (
                            SpecStatus.APPROVED,
                            SpecStatus.PROMOTED,
                            SpecStatus.CONFIRMED_EXISTING,
                        )
                    ),
                )
                .order_by(FeatureSpec.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if feature_spec is None:
            raise DomainError(code="FEATURE_SPEC_MISSING", message="Feature spec required")
        body: dict[str, Any] = {
            "summary": "Close readiness gaps with characterization tests",
            "readiness_reasons": list(assessment.reasons or []),
            "metrics": assessment.metrics,
        }
        lineage = await next_project_key(
            session, cycle.project_id, "implementation_spec", prefix="IMPL-REM"
        )
        row = ImplementationSpec(
            project_id=cycle.project_id,
            lineage_key=lineage,
            version=1,
            status=SpecStatus.PROPOSED,
            kind="REMEDIATION",
            feature_spec_id=feature_spec.id,
            architecture_id=arch.id,
            body=body,
            content_hash=sha256_hex(body),
            conformance_report={"gaps": assessment.reasons},
        )
        session.add(row)
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="implementation_spec",
            aggregate_id=row.id,
            event_type="implementation_spec.proposed",
            payload={"kind": "REMEDIATION", "cycle_id": str(cycle_id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=cycle.project_id,
            delivery_cycle_id=cycle_id,
        )
        return row

    async def approve_and_schedule_forge(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        impl_spec_id: uuid.UUID,
        ctx: CommandContext,
    ) -> uuid.UUID:
        if ActorRole.APPROVER not in ctx.actor.roles:
            raise Unauthorized("Implementation spec approval requires APPROVER")
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None:
            raise DomainError(code="NOT_FOUND", message="Cycle not found")
        impl = await session.get(ImplementationSpec, impl_spec_id)
        if impl is None or impl.kind != "REMEDIATION":
            raise DomainError(code="NOT_FOUND", message="Remediation ImplementationSpec missing")
        spec_svc = ImplementationSpecService()
        approval_id = await spec_svc.request_approval(session, impl.id, cycle_id, ctx)
        policy = await ensure_policy_version(session)
        approval = await ApprovalService(policy=policy).decide(
            session, approval_id, ApprovalStatus.APPROVED, "brownfield remediation", ctx
        )
        await spec_svc.on_approved(session, impl.id, approval.id, ctx)
        from core.domain.repositories.models import Repository

        repo = await session.get(Repository, cycle.repository_id) if cycle.repository_id else None
        if repo is None or repo.canonical_commit is None:
            raise DomainError(code="REPOSITORY_NOT_READY", message="Repository not ready")
        task = await TaskService().create_task(
            session,
            cycle_id,
            "Remediation — add characterization coverage",
            WorkType.CODE_CHANGE,
            TaskOrigin.REMEDIATION,
            ctx,
        )
        task.implementation_spec_id = impl.id
        await session.flush()
        body = TaskContractBody(
            objective=impl.body.get("summary", "Remediation"),
            work_type=WorkType.CODE_CHANGE,
            repository_id=cycle.repository_id,
            base_policy="EXPLICIT_SHA",
            base_commit=repo.canonical_commit,
            allowed_scope=["tests/**", "src/**"],
            allowed_actions=[
                "repo.read",
                "repo.write",
                "git.status",
                "git.diff",
                "git.commit",
                "test.run",
            ],
            required_outputs=["candidate_commit"],
            inputs=[VersionedRef(ref_type="IMPLEMENTATION_SPEC", ref_id=impl.id)],
            executor_kind="AGENT_RUNTIME",
            agent_profile="forge.implementation",
        )
        contract = await ContractService().create_draft(
            session, task.id, body, "compiler:brownfield.remediation", ctx
        )
        await ContractService().issue(session, contract.id, ctx)
        await TaskService().mark_ready(session, task.id, ctx)
        return task.id

    async def after_reintegration(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> None:
        """Re-run baseline proposals/execution at the post-remediation canonical SHA."""
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is not None and cycle.repository_id is not None:
            from core.domain.repositories.models import Repository

            repo = await session.get(Repository, cycle.repository_id)
            if repo is not None and repo.canonical_commit:
                cycle.base_sha = repo.canonical_commit
                await session.flush()
        await BaselineOrchestrator().run_baseline_stage(session, cycle_id, ctx)
        from core.intelligence.baselines.readiness import ReadinessService

        await ReadinessService().assess(session, cycle_id, ctx, recompute=True)

    async def find_open_remediation_impl(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
    ) -> ImplementationSpec | None:
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None:
            return None
        return (
            await session.execute(
                select(ImplementationSpec)
                .where(
                    ImplementationSpec.project_id == cycle.project_id,
                    ImplementationSpec.kind == "REMEDIATION",
                    ImplementationSpec.status.in_((SpecStatus.PROPOSED, SpecStatus.APPROVED)),
                )
                .order_by(ImplementationSpec.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def _latest_assessment(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
    ) -> ReadinessAssessment | None:
        return (
            await session.execute(
                select(ReadinessAssessment)
                .where(ReadinessAssessment.delivery_cycle_id == cycle_id)
                .order_by(ReadinessAssessment.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
