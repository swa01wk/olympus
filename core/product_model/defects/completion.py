"""Post-execution handlers for bug-fix agent and deterministic stages."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import DeliveryCycleType
from core.domain.executions.models import Execution
from core.execution.artifacts import ArtifactStore
from core.product_model.defects.orchestrator import BugFixOrchestrator
from core.product_model.defects.schemas import (
    DefectTriage,
    ExpectedBehaviorProposal,
    ReproductionTestArtifact,
    RootCauseHypothesis,
)
from core.product_model.defects.service import DefectService


class BugFixCompletionService:
    async def persist_from_execution(
        self,
        session: AsyncSession,
        execution: Execution,
        profile: str,
        output: dict[str, Any],
        ctx: CommandContext,
    ) -> None:
        cycle = await session.get(DeliveryCycle, execution.delivery_cycle_id)
        if cycle is None or cycle.type != DeliveryCycleType.BUG_FIX:
            return
        orch = BugFixOrchestrator()
        svc = DeliveryCycleService()
        if profile == "kira.defect_triage":
            triage = DefectTriage.model_validate(output)
            await DefectService().persist_triage(session, cycle.id, triage, execution.id, ctx)
            if cycle.state == "TRIAGE":
                allowed = await svc.allowed_commands(session, cycle, ctx)
                if any(c.get("command") == "start_reproduction" for c in allowed):
                    cmd = next(c for c in allowed if c.get("command") == "start_reproduction")
                    if cmd.get("allowed"):
                        await svc.run_command(
                            session, cycle.id, "start_reproduction", cycle.state, ctx
                        )
        elif profile == "sentinel.reproduce":
            from core.domain.artifacts.models import Artifact

            artifact_payload = ReproductionTestArtifact.model_validate(output)
            store = ArtifactStore()
            existing_art = (
                await session.execute(
                    select(Artifact).where(
                        Artifact.execution_id == execution.id,
                        Artifact.kind == "REPRODUCTION_TEST",
                    )
                )
            ).scalar_one_or_none()
            if existing_art is not None:
                art = existing_art
            else:
                art = await store.put(
                    session,
                    project_id=cycle.project_id,
                    delivery_cycle_id=cycle.id,
                    execution_id=execution.id,
                    kind="REPRODUCTION_TEST",
                    schema_name="reproduction_test",
                    schema_version="1",
                    content={
                        "relative_path": artifact_payload.relative_path,
                        "test_source": artifact_payload.test_source,
                    },
                    created_by_actor_id=ctx.actor.id,
                )
            defect = await DefectService().get_by_cycle(session, cycle.id)
            if defect and artifact_payload.observed_symptom_signature:
                triage_payload = dict(defect.triage or {})
                triage_payload["observed_symptom_signature"] = (
                    artifact_payload.observed_symptom_signature
                )
                defect.triage = triage_payload
                await session.flush()
            await orch.schedule_reproduction_run(session, cycle.id, art.id, ctx)
        elif profile == "kira.expected_behavior":
            proposal = ExpectedBehaviorProposal.model_validate(output)
            resolution = await DefectService().persist_expected_behavior(
                session, cycle.id, proposal, execution.id, ctx
            )
            if resolution.approval_id is None and cycle.state == "EXPECTED_BEHAVIOR":
                await svc.run_command(session, cycle.id, "start_root_cause", cycle.state, ctx)
        elif profile == "warden.root_cause":
            from core.domain.task_contracts.models import TaskContract

            hypothesis = RootCauseHypothesis.model_validate(output.get("hypothesis") or output)
            trace_id_raw = output.get("trace_correlation_id")
            candidates_json = "[]"
            task_contract = (
                await session.execute(
                    select(TaskContract)
                    .where(TaskContract.task_id == execution.task_id)
                    .order_by(TaskContract.version.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if task_contract and isinstance(task_contract.body, dict):
                snap = task_contract.body.get("_snapshot") or {}
                trace_id_raw = trace_id_raw or snap.get("trace_correlation_id")
                candidates_json = str(snap.get("candidates_json") or "[]")
            trace_id = uuid.UUID(str(trace_id_raw))
            candidates = json.loads(candidates_json)
            candidate_keys = {c.get("stable_key") for c in candidates if c.get("stable_key")}
            rca = await DefectService().persist_root_cause(
                session,
                cycle.id,
                hypothesis,
                trace_id,
                execution.id,
                ctx,
                candidate_keys=candidate_keys,
            )
            from core.intelligence.impact.engine import ImpactEngine
            from core.traceability.models import RepositoryIndexPointer

            pointer = await session.get(RepositoryIndexPointer, cycle.repository_id)
            if pointer and pointer.canonical_index_version_id:
                ia = await ImpactEngine().assess(
                    session,
                    cycle.id,
                    seed_stable_keys=hypothesis.faulty_stable_keys,
                    index_version_id=pointer.canonical_index_version_id,
                    ctx=ctx,
                )
                rca.impact_assessment_id = ia.id
                await session.flush()
            await orch.schedule_repair_implementation_spec(session, cycle.id, ctx)

    async def maybe_start_task_plan_after_repair_impl_approval(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> None:
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None or cycle.type != DeliveryCycleType.BUG_FIX:
            return
        if cycle.state != "ROOT_CAUSE":
            return
        from core.planning.models import TaskPlanRow

        existing = (
            await session.execute(
                select(TaskPlanRow.id).where(
                    TaskPlanRow.delivery_cycle_id == cycle_id,
                    TaskPlanRow.status.in_(("PROPOSED", "ACCEPTED")),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return
        await BugFixOrchestrator().schedule_repair_task_plan(session, cycle_id, ctx)

    async def maybe_advance_to_development_after_repair_plan(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> None:
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None or cycle.state != "ROOT_CAUSE":
            return
        svc = DeliveryCycleService()
        allowed = await svc.allowed_commands(session, cycle, ctx)
        cmd = next((c for c in allowed if c.get("command") == "start_development"), None)
        if cmd and cmd.get("allowed"):
            await svc.run_command(session, cycle_id, "start_development", cycle.state, ctx)

    async def after_reproduction_run(
        self,
        session: AsyncSession,
        execution: Execution,
        output: dict[str, Any],
        ctx: CommandContext,
    ) -> None:
        cycle = await session.get(DeliveryCycle, execution.delivery_cycle_id)
        if cycle is None or cycle.type != DeliveryCycleType.BUG_FIX:
            return
        svc = DeliveryCycleService()
        if (
            cycle.state == "REPRODUCTION"
            and output.get("reproduced")
            and output.get("phase") == "PRE_REPAIR"
        ):
            allowed = await svc.allowed_commands(session, cycle, ctx)
            cmd = next(
                (c for c in allowed if c.get("command") == "resolve_expected_behavior"),
                None,
            )
            if cmd and cmd.get("allowed"):
                await svc.run_command(
                    session, cycle.id, "resolve_expected_behavior", cycle.state, ctx
                )
        elif cycle.state == "EXPECTED_BEHAVIOR":
            pass
        elif cycle.state == "REGRESSION":
            phase = output.get("phase")
            if phase == "POST_REPAIR" and output.get("reproduced"):
                test_path = await BugFixOrchestrator()._regression_test_path_for_cycle(
                    session, cycle.id
                )
                from core.integration.enums import ICStatus
                from core.integration.models import IntegrationCandidate

                ic = (
                    await session.execute(
                        select(IntegrationCandidate)
                        .where(
                            IntegrationCandidate.delivery_cycle_id == cycle.id,
                            IntegrationCandidate.status == ICStatus.READY,
                        )
                        .order_by(IntegrationCandidate.created_at.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if ic and test_path:
                    await BugFixOrchestrator().schedule_regression_test_run(
                        session,
                        cycle.id,
                        test_path,
                        ic.integrated_sha or "",
                        ctx,
                        integration_candidate_id=ic.id,
                    )
            elif output.get("passed") and output.get("phase") == "REGRESSION":
                defect = await DefectService().get_by_cycle(session, cycle.id)
                from core.integration.enums import ICStatus
                from core.integration.models import IntegrationCandidate

                ic = (
                    await session.execute(
                        select(IntegrationCandidate)
                        .where(
                            IntegrationCandidate.delivery_cycle_id == cycle.id,
                            IntegrationCandidate.status == ICStatus.READY,
                        )
                        .order_by(IntegrationCandidate.created_at.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                test_path = await BugFixOrchestrator()._regression_test_path_for_cycle(
                    session, cycle.id
                )
                if defect and ic and test_path:
                    await BugFixOrchestrator().schedule_regression_test_run(
                        session,
                        cycle.id,
                        test_path,
                        defect.affected_sha,
                        ctx,
                        integration_candidate_id=ic.id,
                        validate_at_affected=True,
                    )
            elif output.get("validation") and not output.get("passed"):
                from core.assurance.reproduction.regression import finalize_regression_gates

                await finalize_regression_gates(session, cycle.id, ctx)
                allowed = await svc.allowed_commands(session, cycle, ctx)
                cmd = next((c for c in allowed if c.get("command") == "start_assurance"), None)
                if cmd and cmd.get("allowed"):
                    await svc.run_command(session, cycle.id, "start_assurance", cycle.state, ctx)
