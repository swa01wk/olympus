from __future__ import annotations

import pytest
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.enums import ExecutionStatus, TaskStatus
from core.domain.executions.models import Execution
from core.domain.task_contracts.schemas import TaskContractBody
from core.domain.tasks.models import Task
from core.execution.worker import ExecutionWorker
from core.scheduler.admission import AdmissionService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.execution_harness import seed_ready_task

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_retry_creates_new_execution(async_engine) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    task_id = None
    actor_id = None
    first_id = None

    async with factory() as session, session.begin():
        body = TaskContractBody(
            objective="fail once",
            work_type="ANALYSIS",
            inputs=[],
            executor_kind="DETERMINISTIC",
            deterministic_executor="noop.fail",
        )
        bundle = await seed_ready_task(session, key_prefix="retry", body=body)
        bundle.task.max_attempts = 3
        task_id = bundle.task.id
        actor_id = bundle.actor.id
        ctx = CommandContext(actor=bundle.actor, correlation_id="retry-1")
        first = await AdmissionService().admit_task(session, task_id, ctx)
        first_id = first.id
        worker = ExecutionWorker(worker_id="retry-w")
        await worker.run_once(session, ctx)
        await session.refresh(first)
        assert first.status == ExecutionStatus.FAILED

    async with factory() as session, session.begin():
        actor = await session.get(Actor, actor_id)
        task = await session.get(Task, task_id)
        assert task is not None
        assert task.status == TaskStatus.READY
        ctx = CommandContext(actor=actor, correlation_id="retry-2")  # type: ignore[arg-type]
        second = await AdmissionService().admit_task(session, task_id, ctx)
        assert second.attempt_number == 2
        assert second.previous_execution_id is None

    async with factory() as session:
        rows = (
            await session.execute(select(Execution).where(Execution.task_id == task_id))
        ).scalars()
        by_attempt = {row.attempt_number: row for row in rows}
        assert len(by_attempt) == 2
        assert by_attempt[1].id == first_id
        assert by_attempt[1].status == ExecutionStatus.FAILED
        assert by_attempt[2].status == ExecutionStatus.QUEUED
