from __future__ import annotations

import pytest
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import DeliveryCycleType, TaskOrigin
from core.domain.executions.models import Execution
from core.execution.snapshots.builder import SnapshotBuilder
from core.planning.task_plans.service import TaskPlanService
from tests.fixtures.planning_workflow_harness import (
    build_task_plan_for_cycle,
    provision_greenfield_repository,
    seed_approved_architecture,
    seed_approved_implementation_specs_for_cycle,
    seed_supportdesk_product_and_approved_scope,
)

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_snapshot_includes_architecture_and_implementation_spec_versions(
    db_session, sample_project, system_ctx, operator_ctx
) -> None:
    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "snap",
        system_ctx,
    )
    await seed_supportdesk_product_and_approved_scope(
        db_session, sample_project.id, cycle.id, operator_ctx
    )
    await seed_approved_architecture(db_session, sample_project.id, system_ctx)
    await provision_greenfield_repository(db_session, cycle, system_ctx)
    cycle.state = "PLANNING"
    await db_session.flush()
    impl_specs = await seed_approved_implementation_specs_for_cycle(
        db_session, cycle.id, system_ctx
    )
    plan = await build_task_plan_for_cycle(db_session, cycle.id, impl_specs)
    plan_row = await TaskPlanService().persist_proposed(
        db_session,
        delivery_cycle_id=cycle.id,
        plan=plan,
        implementation_spec_ids=[s.id for s in impl_specs],
        execution_id=None,
        ctx=system_ctx,
    )
    await TaskPlanService().accept(db_session, plan_row.id, system_ctx)

    from core.domain.tasks.models import Task as TaskModel
    from sqlalchemy import select

    tasks = await db_session.execute(
        select(TaskModel).where(
            TaskModel.delivery_cycle_id == cycle.id,
            TaskModel.origin == TaskOrigin.IMPLEMENTATION_PLAN,
        )
    )
    task = tasks.scalars().first()
    assert task is not None and task.current_contract_id is not None

    from core.domain.task_contracts.models import TaskContract

    contract = await db_session.get(TaskContract, task.current_contract_id)
    assert contract is not None
    execution = Execution(
        key="E-SNAP",
        task_id=task.id,
        delivery_cycle_id=cycle.id,
        task_contract_id=contract.id,
        attempt_number=1,
        status="QUEUED",
        executor_kind="AGENT_RUNTIME",
    )
    db_session.add(execution)
    await db_session.flush()

    snapshot = await SnapshotBuilder().build(db_session, execution)
    content = snapshot.content
    assert content.get("architecture_versions")
    assert content.get("implementation_spec_versions")
