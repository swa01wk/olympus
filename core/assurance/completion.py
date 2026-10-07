"""Persist assurance agent outputs and chain sentinel execution."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.coverage import CoverageService
from core.assurance.deterministic_plan import build_plan_from_verifies_links
from core.assurance.enums import (
    EvidenceProducer,
    EvidenceResult,
    EvidenceType,
    VerificationPlanStatus,
)
from core.assurance.evidence import EvidenceService
from core.assurance.findings import FindingService, compute_fingerprint
from core.assurance.gates import GateFinalizerService
from core.assurance.models import VerificationPlanRow, WardenReviewRecord
from core.assurance.orchestrator import AssuranceOrchestrator
from core.assurance.plan_validation import PlanValidationService
from core.assurance.schemas import SentinelRecommendation, VerificationPlan, WardenReview
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.executions.models import Execution
from core.domain.task_contracts.schemas import TaskContractBody
from core.execution.artifacts import ArtifactStore
from core.integration.enums import FindingSeverity, FindingSource
from core.integration.models import IntegrationCandidate
from core.policy.policy_service import get_cached_policy_content


class AssuranceCompletionService:
    async def persist_from_execution(
        self,
        session: AsyncSession,
        execution: Execution,
        profile: str,
        output: dict[str, Any],
        ctx: CommandContext,
    ) -> None:
        if profile == "warden.review":
            await self._persist_warden(session, execution, output, ctx)
        elif profile == "sentinel.plan":
            await self._persist_sentinel_plan(session, execution, output, ctx)
        elif profile == "sentinel.summarize":
            await self._persist_sentinel_summary(session, execution, output, ctx)

    async def after_deterministic_verification(
        self,
        session: AsyncSession,
        execution: Execution,
        ctx: CommandContext,
    ) -> None:
        ic_id = await self._ic_from_contract(session, execution)
        if ic_id is None:
            return
        await CoverageService().recompute_for_ic(session, ic_id, ctx)
        await self._try_finalize_gates(session, ic_id, ctx)

    async def _persist_warden(
        self,
        session: AsyncSession,
        execution: Execution,
        output: dict[str, Any],
        ctx: CommandContext,
    ) -> None:
        review = WardenReview.model_validate(output.get("review") or output)
        ic_id = await self._ic_from_contract(session, execution)
        if ic_id is None:
            return
        ic = await session.get(IntegrationCandidate, ic_id)
        cycle = await session.get(DeliveryCycle, execution.delivery_cycle_id)
        if ic is None or cycle is None or ic.integrated_sha is None:
            return
        store = ArtifactStore()
        artifact = await store.put(
            session,
            project_id=cycle.project_id,
            delivery_cycle_id=cycle.id,
            execution_id=execution.id,
            kind="WARDEN_REVIEW",
            schema_name="WardenReview",
            schema_version="1",
            content=review.model_dump(mode="json"),
        )
        session.add(
            WardenReviewRecord(
                integration_candidate_id=ic.id,
                execution_id=execution.id,
                recommendation=review.recommendation,
                summary=review.summary,
                artifact_id=artifact.id,
            )
        )
        finding_svc = FindingService()
        for draft in review.findings:
            fp = compute_fingerprint(
                FindingSource.WARDEN.value,
                draft.category,
                [{"file_path": draft.file_path, "line_start": draft.line_start}],
            )
            await finding_svc.create(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                source=FindingSource.WARDEN,
                category=draft.category,
                severity=FindingSeverity(draft.severity),
                title=draft.title,
                detail={"detail": draft.detail, "spec_refs": draft.spec_refs},
                ctx=ctx,
                integration_candidate_id=ic.id,
                commit_sha=ic.integrated_sha,
                code_refs=[{"file_path": draft.file_path, "line_start": draft.line_start}],
                spec_refs=draft.spec_refs,
                producer_execution_id=execution.id,
                fingerprint=fp,
            )
        policy = get_cached_policy_content().get("assurance", {})
        if (
            policy.get("warden_unspecified_concern_as_finding", True)
            and review.recommendation == "REQUEST_CHANGES"
            and not review.findings
        ):
            await finding_svc.create(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                source=FindingSource.WARDEN,
                category="WARDEN_UNSPECIFIED_CONCERN",
                severity=FindingSeverity.MAJOR,
                title="Warden requested changes without specific findings",
                detail={"summary": review.summary},
                ctx=ctx,
                integration_candidate_id=ic.id,
                commit_sha=ic.integrated_sha,
                producer_execution_id=execution.id,
            )
        await EvidenceService().record(
            session,
            project_id=cycle.project_id,
            delivery_cycle_id=cycle.id,
            integration_candidate_id=ic.id,
            commit_sha=ic.integrated_sha,
            evidence_type=EvidenceType.STATIC_REVIEW,
            result=EvidenceResult.PASS,
            subject_type="IC",
            subject_id=ic.id,
            check_ref=str(artifact.id),
            producer=EvidenceProducer.WARDEN,
            ctx=ctx,
            check_artifact_id=artifact.id,
            execution_id=execution.id,
        )
        await self._try_finalize_gates(session, ic.id, ctx)

    async def _persist_sentinel_plan(
        self,
        session: AsyncSession,
        execution: Execution,
        output: dict[str, Any],
        ctx: CommandContext,
    ) -> None:
        ic_id = await self._ic_from_contract(session, execution)
        if ic_id is None:
            return
        plan_data = output.get("verification_plan") or output.get("plan") or output
        try:
            plan = VerificationPlan.model_validate(plan_data)
        except Exception:
            plan = await build_plan_from_verifies_links(session, ic_id)
        ok, report = await PlanValidationService().validate(session, ic_id, plan)
        row = VerificationPlanRow(
            integration_candidate_id=ic_id,
            execution_id=execution.id,
            status=VerificationPlanStatus.VALIDATED if ok else VerificationPlanStatus.REJECTED,
            validation_report={**report, "plan": plan.model_dump(mode="json")},
        )
        session.add(row)
        await session.flush()
        if ok:
            await AssuranceOrchestrator()._schedule_sentinel_execute(session, ic_id, row.id, ctx)

    async def _persist_sentinel_summary(
        self,
        session: AsyncSession,
        execution: Execution,
        output: dict[str, Any],
        ctx: CommandContext,
    ) -> None:
        ic_id = await self._ic_from_contract(session, execution)
        if ic_id is None:
            return
        summary = SentinelRecommendation.model_validate(output.get("recommendation") or output)
        from core.assurance.enums import GateType
        from core.assurance.models import Gate

        gate = (
            await session.execute(
                select(Gate).where(
                    Gate.integration_candidate_id == ic_id,
                    Gate.gate_type == GateType.SENTINEL,
                )
            )
        ).scalar_one_or_none()
        if gate is not None:
            gate.recommendation = summary.model_dump(mode="json")

    async def _try_finalize_gates(
        self,
        session: AsyncSession,
        ic_id: uuid.UUID,
        ctx: CommandContext,
    ) -> None:
        from core.assurance.enums import GateStatus, GateType
        from core.assurance.models import Gate

        gates = await session.execute(
            select(Gate).where(
                Gate.integration_candidate_id == ic_id,
                Gate.status == GateStatus.PENDING,
            )
        )
        finalizer = GateFinalizerService()
        system_ctx = ctx
        for gate in gates.scalars():
            if gate.gate_type == GateType.SENTINEL:
                plan = await session.execute(
                    select(VerificationPlanRow).where(
                        VerificationPlanRow.integration_candidate_id == ic_id,
                        VerificationPlanRow.status == VerificationPlanStatus.VALIDATED,
                    )
                )
                if plan.scalar_one_or_none() is None:
                    continue
            try:
                await finalizer.finalize(session, gate.id, system_ctx)
            except Exception:
                continue

    async def _ic_from_contract(
        self,
        session: AsyncSession,
        execution: Execution,
    ) -> uuid.UUID | None:
        from core.domain.task_contracts.models import TaskContract

        if execution.task_id is None:
            return None
        contract_row = await session.execute(
            select(TaskContract)
            .where(TaskContract.task_id == execution.task_id)
            .order_by(TaskContract.version.desc())
            .limit(1)
        )
        contract = contract_row.scalar_one_or_none()
        if contract is None:
            return None
        body = TaskContractBody.model_validate(contract.body)
        for ref in body.inputs:
            if ref.ref_type == "INTEGRATION_CANDIDATE":
                return ref.ref_id
        return None
