"""Feature-change cycle task scheduling (SYSTEM orchestration)."""

from __future__ import annotations

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import TaskContractStatus, TaskOrigin, WorkType
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody, VersionedRef
from core.domain.tasks.service import TaskService
from core.product_model.changes.service import ChangeRequestService
from core.review.context import RevisionContext
from core.review.contract_snapshot import attach_snapshot


class FeatureChangeOrchestrator:
    async def schedule_change_interpret(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
        *,
        revision: RevisionContext | None = None,
    ) -> dict[str, str]:
        context = await ChangeRequestService().build_interpretation_context(session, cycle_id)
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None:
            raise ValueError("cycle missing")
        task = await TaskService().create_task(
            session,
            cycle_id,
            "Interpret change request",
            WorkType.ANALYSIS,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        body = TaskContractBody(
            objective="Interpret change request against existing feature model",
            work_type=WorkType.ANALYSIS,
            inputs=[VersionedRef(ref_type="DELIVERY_CYCLE", ref_id=cycle_id)],
            repository_id=cycle.repository_id,
            executor_kind="AGENT_RUNTIME",
            agent_profile="kira.change_interpret",
            model_alias="product_decomposition",
            required_outputs=["artifact:CHANGE_INTERPRETATION"],
        )
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body=attach_snapshot(body.model_dump(mode="json"), snapshot=context, revision=revision),
            content_hash=f"change-interpret-{cycle_id}",
            compiled_by="feature_change",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        return {"interpret_task_id": str(task.id)}

    async def schedule_implementation_spec_delta(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
        *,
        revision: RevisionContext | None = None,
    ) -> dict[str, str]:
        from core.intelligence.impact.engine import ImpactEngine
        from core.product_model.specifications.delta import SpecDeltaService

        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None:
            raise ValueError("cycle missing")
        delta = await SpecDeltaService().latest_approved_for_cycle(session, cycle_id)
        if delta is None:
            raise ValueError("approved spec delta missing")
        ia = await ImpactEngine().latest_complete(session, cycle_id)
        cr = await ChangeRequestService().get_by_cycle(session, cycle_id)
        snapshot = {
            "project_name": str(cycle.objective),
            "feature_spec_id": str(delta.to_spec_id),
            "spec_delta_id": str(delta.id),
            "impact_summary": json.dumps(
                {"architecture_delta_suggested": ia.architecture_delta_suggested if ia else False}
            ),
            "implementation_spec_mode": "DELTA",
        }
        task = await TaskService().create_task(
            session,
            cycle_id,
            "Draft implementation spec delta",
            WorkType.ANALYSIS,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        task.governing_ref_id = delta.to_spec_id
        await session.flush()
        body = TaskContractBody(
            objective="Produce ImplementationSpec delta for approved FeatureSpec change",
            work_type=WorkType.ANALYSIS,
            inputs=[VersionedRef(ref_type="FEATURE_SPEC", ref_id=delta.to_spec_id)],
            repository_id=cycle.repository_id,
            executor_kind="AGENT_RUNTIME",
            agent_profile="kira.implementation_spec",
            model_alias="planning",
            required_outputs=["artifact:IMPLEMENTATION_SPEC_DRAFT"],
        )
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body=attach_snapshot(
                body.model_dump(mode="json"),
                snapshot=snapshot,
                revision=revision,
            ),
            content_hash=f"impl-spec-delta-{cycle_id}",
            compiled_by="feature_change",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        if cr is not None:
            await ChangeRequestService().mark_in_delivery(session, cycle_id, ctx)
        return {"implementation_spec_task_id": str(task.id)}

    async def schedule_architecture_delta(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
        *,
        revision: RevisionContext | None = None,
    ) -> dict[str, str]:
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None:
            raise ValueError("cycle missing")
        task = await TaskService().create_task(
            session,
            cycle_id,
            "Propose architecture delta",
            WorkType.ANALYSIS,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        body = TaskContractBody(
            objective="Propose architecture delta for feature change impact",
            work_type=WorkType.ANALYSIS,
            inputs=[VersionedRef(ref_type="DELIVERY_CYCLE", ref_id=cycle_id)],
            repository_id=cycle.repository_id,
            executor_kind="AGENT_RUNTIME",
            agent_profile="atlas.architecture_delta",
            model_alias="architecture",
            required_outputs=["artifact:ARCHITECTURE_DELTA"],
        )
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body=attach_snapshot(body.model_dump(mode="json"), revision=revision),
            content_hash=f"arch-delta-{cycle_id}",
            compiled_by="feature_change",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        return {"architecture_delta_task_id": str(task.id)}
