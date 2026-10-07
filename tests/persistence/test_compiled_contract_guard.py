import pytest
from core.domain.enums import TaskOrigin, WorkType
from core.domain.exceptions import DomainError
from core.domain.task_contracts.schemas import TaskContractBody
from core.domain.task_contracts.service import ContractService
from core.domain.tasks.service import TaskService

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_manual_code_change_contract_rejected_for_implementation_plan(
    db_session, sample_project, operator_ctx
) -> None:
    from core.domain.delivery_cycles.models import DeliveryCycle
    from core.domain.enums import DeliveryCycleType

    cycle = DeliveryCycle(
        project_id=sample_project.id,
        key="C1",
        type=DeliveryCycleType.GREENFIELD_BUILD,
        objective="planning guard test",
        state="PLANNING",
        state_version=0,
        opened_by_actor_id=operator_ctx.actor.id,
    )
    db_session.add(cycle)
    await db_session.flush()
    task = await TaskService().create_task(
        db_session,
        cycle.id,
        "Planned work",
        WorkType.CODE_CHANGE,
        TaskOrigin.IMPLEMENTATION_PLAN,
        operator_ctx,
    )
    body = TaskContractBody(
        objective="x",
        work_type=WorkType.CODE_CHANGE,
        inputs=[],
        executor_kind="AGENT_RUNTIME",
    )
    draft = await ContractService().create_draft(db_session, task.id, body, "manual", operator_ctx)
    with pytest.raises(DomainError) as exc:
        await ContractService().issue(db_session, draft.id, operator_ctx)
    assert exc.value.code == "CONTRACT_COMPILE_REQUIRED"
