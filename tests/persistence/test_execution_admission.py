from __future__ import annotations

import asyncio
import uuid

import pytest
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import (
    ActorKind,
    DeliveryCycleType,
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
from core.scheduler.admission import AdmissionService
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_concurrent_admission_single_execution(async_engine) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as setup, setup.begin():
        actor = Actor(kind=ActorKind.SYSTEM, name="adm", roles=["SYSTEM"])
        setup.add(actor)
        project = Project(key="adm-p", name="Adm")
        setup.add(project)
        await setup.flush()
        ctx = CommandContext(actor=actor, correlation_id="adm")
        cycle = DeliveryCycle(
            project_id=project.id,
            key="C-0001",
            type=DeliveryCycleType.GREENFIELD_BUILD,
            objective="test",
            state="DEVELOPMENT",
            state_version=0,
            opened_by_actor_id=actor.id,
        )
        setup.add(cycle)
        await setup.flush()
        task = await TaskService().create_task(
            setup,
            cycle.id,
            "analysis",
            WorkType.ANALYSIS,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        body = TaskContractBody(
            objective="test",
            work_type=WorkType.ANALYSIS,
            inputs=[],
            executor_kind="DETERMINISTIC",
            deterministic_executor="noop.verify_artifact",
        )
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body=body.model_dump(mode="json"),
            content_hash="abc",
            compiled_by="test",
        )
        setup.add(contract)
        await setup.flush()
        task.current_contract_id = contract.id
        task.status = TaskStatus.READY
        await setup.flush()
        task_id = task.id
        actor_id = actor.id

    admission = AdmissionService()

    async def admit_once() -> None:
        async with factory() as session, session.begin():
            actor_row = await session.get(Actor, actor_id)
            assert actor_row is not None
            ctx = CommandContext(actor=actor_row, correlation_id=str(uuid.uuid4()))
            await admission.admit_batch(session, 5, ctx)

    await asyncio.gather(admit_once(), admit_once())

    async with factory() as session, session.begin():
        count = await session.scalar(
            select(func.count()).select_from(Execution).where(Execution.task_id == task_id)
        )
        assert count == 1
        for row in (
            await session.execute(select(Execution).where(Execution.task_id == task_id))
        ).scalars():
            await session.delete(row)
        task_row = await session.get(Task, task_id)
        if task_row is not None:
            task_row.status = TaskStatus.READY
