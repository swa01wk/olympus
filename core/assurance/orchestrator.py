"""Assurance sequencing when an IC becomes READY."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.deterministic_plan import build_plan_from_verifies_links
from core.assurance.enums import (
    EvidenceProducer,
    EvidenceResult,
    EvidenceType,
    VerificationPlanStatus,
)
from core.assurance.evidence import EvidenceService
from core.assurance.gates import GateService
from core.assurance.models import VerificationObligation, VerificationPlanRow
from core.assurance.obligations import ObligationService
from core.assurance.plan_validation import PlanValidationService
from core.commands.context import CommandContext
from core.domain.canonical_json import sha256_hex
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import TaskContractStatus, TaskOrigin, WorkType
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody, VersionedRef
from core.domain.tasks.service import TaskService
from core.integration.models import IntegrationCandidate
from core.policy.policy_service import get_cached_policy_content


class AssuranceOrchestrator:
    async def on_integration_ready(
        self,
        session: AsyncSession,
        ic_id: uuid.UUID,
        ctx: CommandContext,
    ) -> dict[str, object]:
        ic = await session.get(IntegrationCandidate, ic_id)
        if ic is None or ic.integrated_sha is None:
            raise ValueError("IC not READY")
        cycle = await session.get(DeliveryCycle, ic.delivery_cycle_id)
        if cycle is None:
            raise ValueError("cycle missing")
        if (
            await session.execute(
                select(VerificationObligation.id).where(
                    VerificationObligation.integration_candidate_id == ic.id,
                )
            )
        ).first() is None:
            await ObligationService().derive(session, ic.id, ctx)
        if ic.supersedes_id:
            from core.assurance.carry_forward import EvidenceCarryForwardService
            from core.assurance.impacted import ImpactedVerificationService

            await ImpactedVerificationService().mark_impacted(session, ic, ic.supersedes_id)
            await EvidenceCarryForwardService().carry_from_superseded(
                session, ic, ic.supersedes_id, ctx
            )
        from core.assurance.finding_resolution import FindingResolutionService

        await FindingResolutionService().resolve_for_ic(session, ic, ctx)
        from core.assurance.models import Gate

        if (
            await session.execute(select(Gate.id).where(Gate.integration_candidate_id == ic.id))
        ).first() is None:
            await GateService().create_pending_gates(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                integration_candidate_id=ic.id,
                cycle_type_value=cycle.type.value,
                ctx=ctx,
            )
        if ic.checks_artifact_id:
            await EvidenceService().record(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                integration_candidate_id=ic.id,
                commit_sha=ic.integrated_sha,
                evidence_type=EvidenceType.INTEGRATION_CHECK,
                result=EvidenceResult.PASS,
                subject_type="IC",
                subject_id=ic.id,
                check_ref=str(ic.checks_artifact_id),
                producer=EvidenceProducer.INTEGRATION,
                ctx=ctx,
                check_artifact_id=ic.checks_artifact_id,
            )
        policy = get_cached_policy_content().get("assurance", {})
        scheduled: list[str] = []
        if policy.get("auto_schedule_warden", True):
            scheduled.append(await self._schedule_warden(session, ic, cycle, ctx))
        if policy.get("auto_schedule_sentinel", True):
            scheduled.append(await self._schedule_sentinel_plan(session, ic, cycle, ctx))
        if policy.get("use_deterministic_plan_fallback", True):
            await self._seed_validated_plan(session, ic.id, ctx)
        return {"ic_id": str(ic.id), "scheduled": scheduled}

    async def _seed_validated_plan(
        self,
        session: AsyncSession,
        ic_id: uuid.UUID,
        ctx: CommandContext,
    ) -> None:
        existing = await session.execute(
            select(VerificationPlanRow).where(
                VerificationPlanRow.integration_candidate_id == ic_id,
                VerificationPlanRow.status == VerificationPlanStatus.VALIDATED,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return
        draft = await build_plan_from_verifies_links(session, ic_id)
        ok, report = await PlanValidationService().validate(session, ic_id, draft)
        if not ok or not draft.checks:
            return
        row = VerificationPlanRow(
            integration_candidate_id=ic_id,
            status=VerificationPlanStatus.VALIDATED,
            validation_report={
                **report,
                "plan": draft.model_dump(mode="json"),
            },
        )
        session.add(row)
        await session.flush()
        await self._schedule_sentinel_execute(session, ic_id, row.id, ctx)

    async def _schedule_warden(
        self,
        session: AsyncSession,
        ic: IntegrationCandidate,
        cycle: DeliveryCycle,
        ctx: CommandContext,
    ) -> str:
        task = await TaskService().create_task(
            session,
            cycle.id,
            f"Warden review {ic.key}",
            WorkType.ANALYSIS,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        body = TaskContractBody(
            objective="Independent engineering review of integrated change",
            work_type=WorkType.ANALYSIS,
            inputs=[VersionedRef(ref_type="INTEGRATION_CANDIDATE", ref_id=ic.id)],
            repository_id=ic.repository_id,
            executor_kind="AGENT_RUNTIME",
            agent_profile="warden.review",
            model_alias="review",
            required_outputs=["artifact:WARDEN_REVIEW"],
        )
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body=body.model_dump(mode="json"),
            content_hash=sha256_hex(f"warden-{ic.id}"),
            compiled_by="assurance",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        return str(task.id)

    async def _schedule_sentinel_plan(
        self,
        session: AsyncSession,
        ic: IntegrationCandidate,
        cycle: DeliveryCycle,
        ctx: CommandContext,
    ) -> str:
        task = await TaskService().create_task(
            session,
            cycle.id,
            f"Sentinel plan {ic.key}",
            WorkType.ANALYSIS,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        body = TaskContractBody(
            objective="Plan verification checks for integration candidate",
            work_type=WorkType.ANALYSIS,
            inputs=[VersionedRef(ref_type="INTEGRATION_CANDIDATE", ref_id=ic.id)],
            repository_id=ic.repository_id,
            executor_kind="AGENT_RUNTIME",
            agent_profile="sentinel.plan",
            model_alias="verification_planning",
            required_outputs=["artifact:VERIFICATION_PLAN"],
        )
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body=body.model_dump(mode="json"),
            content_hash=sha256_hex(f"sentinel-plan-{ic.id}"),
            compiled_by="assurance",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        return str(task.id)

    async def _schedule_sentinel_execute(
        self,
        session: AsyncSession,
        ic_id: uuid.UUID,
        plan_id: uuid.UUID,
        ctx: CommandContext,
    ) -> str:
        ic = await session.get(IntegrationCandidate, ic_id)
        if ic is None:
            raise ValueError("ic missing")
        cycle = await session.get(DeliveryCycle, ic.delivery_cycle_id)
        if cycle is None:
            raise ValueError("cycle missing")
        task = await TaskService().create_task(
            session,
            cycle.id,
            f"Sentinel execute {ic.key}",
            WorkType.VERIFICATION,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        body = TaskContractBody(
            objective="Execute verification plan checks",
            work_type=WorkType.VERIFICATION,
            inputs=[
                VersionedRef(ref_type="INTEGRATION_CANDIDATE", ref_id=ic.id),
                VersionedRef(ref_type="VERIFICATION_PLAN", ref_id=plan_id),
            ],
            repository_id=ic.repository_id,
            base_policy="EXPLICIT_SHA",
            base_commit=ic.integrated_sha,
            allowed_scope=["**"],
            allowed_actions=["test.run", "shell.run", "repo.read"],
            executor_kind="DETERMINISTIC",
            deterministic_executor="sentinel.execute",
            required_outputs=["artifact:VERIFICATION_EVIDENCE"],
        )
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body=body.model_dump(mode="json"),
            content_hash=sha256_hex(f"sentinel-exec-{ic.id}-{plan_id}"),
            compiled_by="assurance",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        return str(task.id)
