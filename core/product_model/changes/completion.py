from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import DeliveryCycleType
from core.domain.executions.models import Execution
from core.product_model.changes.schemas import ChangeInterpretation
from core.product_model.changes.service import ChangeRequestService


class FeatureChangeCompletionService:
    async def persist_from_execution(
        self,
        session: AsyncSession,
        execution: Execution,
        profile: str,
        output: dict[str, Any],
        ctx: CommandContext,
    ) -> None:
        cycle = await session.get(DeliveryCycle, execution.delivery_cycle_id)
        if cycle is None or cycle.type != DeliveryCycleType.FEATURE_CHANGE:
            return
        if profile == "kira.change_interpret":
            interpretation = ChangeInterpretation.model_validate(output)
            cr = await ChangeRequestService().persist_interpretation(
                session,
                cycle.id,
                interpretation,
                execution.id,
                ctx,
            )
            from core.review.completion import complete_revision_if_needed

            await complete_revision_if_needed(session, execution, cr.id, ctx)
        elif profile == "atlas.architecture_delta":
            from agents.atlas.schemas import ArchitectureDeltaProposal

            from core.planning.architecture.service import ArchitectureService
            from core.review.completion import complete_revision_if_needed

            proposal = ArchitectureDeltaProposal.model_validate(output)
            arch_row = await ArchitectureService().persist_delta(
                session,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
                proposal=proposal,
                execution_id=execution.id,
                ctx=ctx,
            )
            await complete_revision_if_needed(session, execution, arch_row.id, ctx)

    async def maybe_start_impact_after_spec_approval(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> None:
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None or cycle.state != "SPEC_DELTA":
            return
        svc = DeliveryCycleService()
        allowed = await svc.allowed_commands(session, cycle, ctx)
        cmd = next((c for c in allowed if c.get("command") == "start_impact_analysis"), None)
        if cmd and cmd.get("allowed"):
            await svc.run_command(session, cycle.id, "start_impact_analysis", cycle.state, ctx)

    async def maybe_start_task_plan_after_impl_approval(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> None:
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None or cycle.type != DeliveryCycleType.FEATURE_CHANGE:
            return
        if cycle.state != "PLANNING":
            return
        from sqlalchemy import select

        from core.planning.guards import implementation_specs_approved
        from core.planning.models import TaskPlanRow
        from core.planning.orchestrator import PlanningOrchestrator

        guard = await implementation_specs_approved(session, cycle, ctx)
        if not guard.ok:
            return
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
        await PlanningOrchestrator().start_task_plan_generation(session, cycle_id, ctx)
