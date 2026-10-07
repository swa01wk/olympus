from __future__ import annotations

import pytest
from core.commands.context import CommandContext
from core.domain.enums import ExecutionStatus
from core.domain.executions.models import Execution, ExecutionSnapshot
from core.domain.task_contracts.schemas import TaskContractBody
from core.execution.worker import ExecutionWorker
from core.scheduler.admission import AdmissionService
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.execution_harness import seed_ready_task

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_snapshot_immutable(async_engine) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        bundle = await seed_ready_task(session, key_prefix="snap-immut")
        ctx = CommandContext(actor=bundle.actor, correlation_id="snap")
        ex = await AdmissionService().admit_task(session, bundle.task.id, ctx)
        worker = ExecutionWorker(worker_id="snap-w")
        for _ in range(6):
            await worker.run_once(session, ctx)
            await session.refresh(ex)
            if ex.snapshot_id is not None:
                break
        assert ex.snapshot_id is not None
        snap_id = ex.snapshot_id

    async with factory() as session, session.begin():
        row = await session.get(ExecutionSnapshot, snap_id)
        assert row is not None
        with pytest.raises(Exception, match="mutation forbidden|forbidden"):
            await session.execute(
                text("UPDATE execution_snapshots SET snapshot_hash = 'tampered' WHERE id = :id"),
                {"id": snap_id},
            )
            await session.flush()


@pytest.mark.asyncio
async def test_terminal_execution_immutable(async_engine) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    execution_id = None
    async with factory() as session, session.begin():
        body = TaskContractBody(
            objective="fail",
            work_type="ANALYSIS",
            inputs=[],
            executor_kind="DETERMINISTIC",
            deterministic_executor="noop.fail",
        )
        bundle = await seed_ready_task(session, key_prefix="term-immut", body=body)
        ctx = CommandContext(actor=bundle.actor, correlation_id="term")
        ex = await AdmissionService().admit_task(session, bundle.task.id, ctx)
        execution_id = ex.id
        worker = ExecutionWorker(worker_id="term-w")
        for _ in range(4):
            await worker.run_once(session, ctx)
            await session.refresh(ex)
            if ex.status == ExecutionStatus.FAILED:
                break

    assert execution_id is not None
    async with factory() as session, session.begin():
        row = await session.get(Execution, execution_id)
        assert row is not None
        assert row.status == ExecutionStatus.FAILED
        with pytest.raises(Exception, match="terminal execution is immutable"):
            await session.execute(
                text("UPDATE executions SET failure_class = 'TAMPERED' WHERE id = :id"),
                {"id": execution_id},
            )
            await session.flush()
