from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.enums import SpecStatus, TaskContractStatus, TaskOrigin, WorkType
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody, VersionedRef
from core.domain.tasks.service import TaskService
from core.planning.models import Architecture
from core.product_model.models import FeatureSpec, ScopeSet, ScopeSetItem
from core.review.context import RevisionContext
from core.review.contract_snapshot import attach_snapshot


class PlanningOrchestrator:
    async def start_architecture_proposal(
        self,
        session: AsyncSession,
        delivery_cycle_id: uuid.UUID,
        ctx: CommandContext,
        *,
        revision: RevisionContext | None = None,
    ) -> dict[str, str]:
        from core.domain.delivery_cycles.models import DeliveryCycle

        cycle = await session.get(DeliveryCycle, delivery_cycle_id)
        if cycle is None:
            raise ValueError("cycle not found")
        task = await TaskService().create_task(
            session,
            delivery_cycle_id,
            "Propose architecture",
            WorkType.ANALYSIS,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        task.governing_ref_type = "DELIVERY_CYCLE"
        task.governing_ref_id = delivery_cycle_id
        body = TaskContractBody(
            objective="Propose project architecture from approved feature specifications",
            work_type=WorkType.ANALYSIS,
            inputs=[VersionedRef(ref_type="DELIVERY_CYCLE", ref_id=delivery_cycle_id)],
            executor_kind="AGENT_RUNTIME",
            agent_profile="atlas.propose_architecture",
            model_alias="architecture",
            required_outputs=["artifact:ARCHITECTURE_PROPOSAL"],
        )
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body=attach_snapshot(body.model_dump(mode="json"), revision=revision),
            content_hash=f"atlas-{delivery_cycle_id}",
            compiled_by="planning",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        return {"task_id": str(task.id), "contract_id": str(contract.id)}

    async def start_implementation_spec_generation(
        self,
        session: AsyncSession,
        delivery_cycle_id: uuid.UUID,
        ctx: CommandContext,
        *,
        feature_spec_id: uuid.UUID | None = None,
        revision: RevisionContext | None = None,
    ) -> list[dict[str, str]]:
        from core.domain.delivery_cycles.models import DeliveryCycle

        cycle = await session.get(DeliveryCycle, delivery_cycle_id)
        if cycle is None:
            raise ValueError("cycle not found")
        arch = await session.execute(
            select(Architecture)
            .where(
                Architecture.project_id == cycle.project_id,
                Architecture.status == SpecStatus.APPROVED,
            )
            .limit(1)
        )
        if arch.scalar_one_or_none() is None:
            raise ValueError("approved architecture required")

        scope = await session.execute(
            select(ScopeSet)
            .where(ScopeSet.delivery_cycle_id == delivery_cycle_id)
            .order_by(ScopeSet.created_at.desc())
            .limit(1)
        )
        scope_set = scope.scalar_one_or_none()
        if scope_set is None:
            return []
        items = await session.execute(
            select(ScopeSetItem).where(ScopeSetItem.scope_set_id == scope_set.id)
        )
        out: list[dict[str, str]] = []
        for item in items.scalars():
            spec = await session.get(FeatureSpec, item.feature_spec_id)
            if spec is None or spec.status != SpecStatus.APPROVED:
                continue
            if feature_spec_id is not None and spec.id != feature_spec_id:
                continue
            task = await TaskService().create_task(
                session,
                delivery_cycle_id,
                f"Implementation spec for {spec.lineage_key}",
                WorkType.ANALYSIS,
                TaskOrigin.CONTROL_PLANE,
                ctx,
            )
            task.governing_ref_type = "FEATURE_SPEC"
            task.governing_ref_id = spec.id
            body = TaskContractBody(
                objective=f"Draft implementation specification for {spec.lineage_key}",
                work_type=WorkType.ANALYSIS,
                inputs=[
                    VersionedRef(
                        ref_type="FEATURE_SPEC",
                        ref_id=spec.id,
                        version=spec.version,
                        key=spec.lineage_key,
                    )
                ],
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
                body=attach_snapshot(body.model_dump(mode="json"), revision=revision),
                content_hash=f"impl-spec-{spec.id}",
                compiled_by="planning",
            )
            session.add(contract)
            await session.flush()
            task.current_contract_id = contract.id
            await TaskService().mark_ready(session, task.id, ctx)
            out.append({"task_id": str(task.id), "feature_spec_id": str(spec.id)})
        return out

    async def start_task_plan_generation(
        self,
        session: AsyncSession,
        delivery_cycle_id: uuid.UUID,
        ctx: CommandContext,
        *,
        revision: RevisionContext | None = None,
    ) -> dict[str, str]:
        task = await TaskService().create_task(
            session,
            delivery_cycle_id,
            "Generate task plan",
            WorkType.ANALYSIS,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        task.governing_ref_type = "DELIVERY_CYCLE"
        task.governing_ref_id = delivery_cycle_id
        body = TaskContractBody(
            objective="Generate implementation task plan DAG",
            work_type=WorkType.ANALYSIS,
            inputs=[VersionedRef(ref_type="DELIVERY_CYCLE", ref_id=delivery_cycle_id)],
            executor_kind="AGENT_RUNTIME",
            agent_profile="kira.task_plan",
            model_alias="planning",
            required_outputs=["artifact:TASK_PLAN"],
        )
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body=attach_snapshot(body.model_dump(mode="json"), revision=revision),
            content_hash=f"task-plan-{delivery_cycle_id}",
            compiled_by="planning",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        return {"task_id": str(task.id)}
