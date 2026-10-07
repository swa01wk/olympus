from __future__ import annotations

import uuid

import pytest
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import (
    ActorKind,
    DeliveryCycleType,
    ExecutionStatus,
    TaskContractStatus,
    TaskOrigin,
    TaskStatus,
    WorkType,
)
from core.domain.executions.models import Execution
from core.domain.projects.models import Project
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody
from core.domain.tasks.models import Task
from core.domain.tasks.service import TaskService
from core.execution.worker import ExecutionWorker
from core.scheduler.admission import AdmissionService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = [pytest.mark.workflow, pytest.mark.integration]


@pytest.mark.asyncio
async def test_deterministic_execution_completes(async_engine) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session, session.begin():
        actor = Actor(kind=ActorKind.SYSTEM, name="wf-exec", roles=["SYSTEM"])
        session.add(actor)
        project = Project(key="wf-p", name="WF")
        session.add(project)
        await session.flush()
        ctx = CommandContext(actor=actor, correlation_id="wf")
        cycle = DeliveryCycle(
            project_id=project.id,
            key="C-WF1",
            type=DeliveryCycleType.GREENFIELD_BUILD,
            objective="workflow",
            state="DEVELOPMENT",
            state_version=0,
            opened_by_actor_id=actor.id,
        )
        session.add(cycle)
        await session.flush()
        task = await TaskService().create_task(
            session,
            cycle.id,
            "noop",
            WorkType.ANALYSIS,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        body = TaskContractBody(
            objective="noop",
            work_type=WorkType.ANALYSIS,
            inputs=[],
            required_outputs=[],
            executor_kind="DETERMINISTIC",
            deterministic_executor="noop.verify_artifact",
        )
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body=body.model_dump(mode="json"),
            content_hash="deadbeef",
            compiled_by="test",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        task.status = TaskStatus.READY
        await session.flush()
        task_id = task.id
        actor_id = actor.id

    async with factory() as session, session.begin():
        actor_row = await session.get(Actor, actor_id)
        assert actor_row is not None
        ctx = CommandContext(actor=actor_row, correlation_id="wf-run")
        execution = await AdmissionService().admit_task(session, task_id, ctx)
        execution_id = execution.id
        worker = ExecutionWorker(worker_id=f"test-{uuid.uuid4().hex[:6]}")
        for _ in range(8):
            await worker.run_once(session, ctx)
            await session.refresh(execution)
            if execution.status == ExecutionStatus.COMPLETED:
                break

    async with factory() as session:
        execution = await session.get(Execution, execution_id)
        assert execution is not None
        assert execution.status == ExecutionStatus.COMPLETED
        task = await session.get(Task, task_id)
        assert task is not None
        assert task.status == TaskStatus.COMPLETED
