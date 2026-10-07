from __future__ import annotations

import pytest
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import DeliveryCycleType, TaskContractStatus, TaskOrigin, WorkType
from core.domain.task_contracts.schemas import TaskContractBody
from core.domain.task_contracts.service import ContractService
from core.domain.tasks.service import TaskService
from sqlalchemy import text

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_issued_contract_body_immutable_in_db(
    db_session, sample_project, operator_ctx
) -> None:
    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "obj",
        operator_ctx,
    )
    task = await TaskService().create_task(
        db_session,
        cycle.id,
        "T",
        WorkType.ANALYSIS,
        TaskOrigin.CONTROL_PLANE,
        operator_ctx,
    )
    body = TaskContractBody(
        objective="do",
        work_type=WorkType.ANALYSIS,
        inputs=[],
        executor_kind="DETERMINISTIC",
    )
    contract = await ContractService().create_draft(
        db_session, task.id, body, "manual", operator_ctx
    )
    await ContractService().issue(db_session, contract.id, operator_ctx)
    with pytest.raises(Exception, match="immutable|issued"):
        await db_session.execute(
            text("UPDATE task_contracts SET body = '{\"x\": 1}'::jsonb WHERE id = :id"),
            {"id": contract.id},
        )
        await db_session.flush()


@pytest.mark.asyncio
async def test_supersede_allowed(db_session, sample_project, operator_ctx) -> None:
    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "obj",
        operator_ctx,
    )
    task = await TaskService().create_task(
        db_session,
        cycle.id,
        "T2",
        WorkType.ANALYSIS,
        TaskOrigin.CONTROL_PLANE,
        operator_ctx,
    )
    body = TaskContractBody(
        objective="do",
        work_type=WorkType.ANALYSIS,
        inputs=[],
        executor_kind="DETERMINISTIC",
    )
    c1 = await ContractService().create_draft(db_session, task.id, body, "manual", operator_ctx)
    await ContractService().issue(db_session, c1.id, operator_ctx)
    c2 = await ContractService().create_draft(db_session, task.id, body, "manual", operator_ctx)
    await ContractService().issue(db_session, c2.id, operator_ctx)
    await db_session.refresh(c1)
    assert c1.status == TaskContractStatus.SUPERSEDED
