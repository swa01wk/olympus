from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.enums import ExecutionStatus, TaskStatus
from core.domain.executions.models import Execution, ExecutionLease
from core.domain.task_contracts.schemas import TaskContractBody
from core.domain.tasks.models import Task
from core.execution.leases.manager import LeaseManager
from core.execution.leases.sweeper import LeaseSweeper
from core.execution.service import ExecutionService
from core.execution.snapshots.builder import SnapshotBuilder
from core.execution.worker import ExecutionWorker
from core.scheduler.admission import AdmissionService
from core.state.transition_service import TransitionService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.execution_harness import seed_ready_task

pytestmark = [pytest.mark.recovery, pytest.mark.integration]


@pytest.mark.asyncio
async def test_expired_lease_before_start_requeues(async_engine) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    execution_id = None
    actor_id = None
    async with factory() as session, session.begin():
        bundle = await seed_ready_task(session, key_prefix="rec-pre")
        ctx = CommandContext(actor=bundle.actor, correlation_id="rec-pre")
        ex = await AdmissionService().admit_task(session, bundle.task.id, ctx)
        execution_id = ex.id
        actor_id = bundle.actor.id
        lease = await LeaseManager().claim(session, "worker-a", ctx)
        assert lease is not None
        assert ex.status == ExecutionStatus.LEASED

    async with factory() as session, session.begin():
        lease = (
            await session.execute(
                select(ExecutionLease).where(ExecutionLease.execution_id == execution_id)
            )
        ).scalar_one()
        lease.expires_at = datetime.now(UTC) - timedelta(seconds=30)
        actor = await session.get(Actor, actor_id)
        ctx = CommandContext(actor=actor, correlation_id="sweep-pre")  # type: ignore[arg-type]
        assert await LeaseSweeper().sweep_expired(session, ctx) == 1

    async with factory() as session:
        ex = await session.get(Execution, execution_id)
        assert ex is not None
        assert ex.status == ExecutionStatus.QUEUED

    async with factory() as session, session.begin():
        actor = await session.get(Actor, actor_id)
        ctx = CommandContext(actor=actor, correlation_id="finish-pre")  # type: ignore[arg-type]
        worker = ExecutionWorker(worker_id="worker-b")
        for _ in range(4):
            await worker.run_once(session, ctx)
        ex = await session.get(Execution, execution_id)
        assert ex is not None
        assert ex.status == ExecutionStatus.COMPLETED


@pytest.mark.asyncio
async def test_expired_lease_after_start_fails_and_retries(async_engine) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    task_id = None
    actor_id = None
    first_id = None
    async with factory() as session, session.begin():
        bundle = await seed_ready_task(session, key_prefix="rec-post")
        bundle.task.max_attempts = 3
        task_id = bundle.task.id
        actor_id = bundle.actor.id
        ctx = CommandContext(actor=bundle.actor, correlation_id="rec-post")
        ex = await AdmissionService().admit_task(session, bundle.task.id, ctx)
        first_id = ex.id
        lease = await LeaseManager().claim(session, "worker-c", ctx)
        assert lease is not None
        await SnapshotBuilder().build(session, ex)
        await ExecutionService().transition(session, ex.id, "start", ctx, lease_id=lease.id)
        await TransitionService().transition(
            session,
            "task",
            bundle.task.id,
            TaskStatus.QUEUED.value,
            "start_execution",
            ctx,
        )
        await session.refresh(ex)
        assert ex.status == ExecutionStatus.STARTED
        lease.expires_at = datetime.now(UTC) - timedelta(seconds=30)
        assert await LeaseSweeper().sweep_expired(session, ctx) == 1
        await session.refresh(ex)
        assert ex.status == ExecutionStatus.FAILED
        assert ex.failure_class == "LEASE_EXPIRED"

    async with factory() as session, session.begin():
        actor = await session.get(Actor, actor_id)
        ctx = CommandContext(actor=actor, correlation_id="rec-retry")  # type: ignore[arg-type]
        second = await AdmissionService().admit_task(session, task_id, ctx)
        worker = ExecutionWorker(worker_id="worker-d")
        for _ in range(4):
            await worker.run_once(session, ctx)
            await session.refresh(second)
            if second.status == ExecutionStatus.COMPLETED:
                break

    async with factory() as session:
        rows = list(
            (await session.execute(select(Execution).where(Execution.task_id == task_id))).scalars()
        )
        assert len(rows) == 2
        failed = next(r for r in rows if r.id == first_id)
        assert failed.status == ExecutionStatus.FAILED
        done = next(r for r in rows if r.attempt_number == 2)
        assert done.status == ExecutionStatus.COMPLETED
        task = await session.get(Task, task_id)
        assert task is not None
        assert task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_wall_clock_timeout(async_engine) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        body = TaskContractBody(
            objective="slow",
            work_type="ANALYSIS",
            inputs=[],
            executor_kind="DETERMINISTIC",
            deterministic_executor="noop.sleep_past_wall_clock",
            timeouts={"wall_clock_s": 1},
        )
        bundle = await seed_ready_task(session, key_prefix="rec-timeout", body=body)
        ctx = CommandContext(actor=bundle.actor, correlation_id="timeout")
        ex = await AdmissionService().admit_task(session, bundle.task.id, ctx)
        worker = ExecutionWorker(worker_id="worker-timeout")
        await worker.run_once(session, ctx)
        await session.refresh(ex)
        assert ex.status == ExecutionStatus.TIMED_OUT
