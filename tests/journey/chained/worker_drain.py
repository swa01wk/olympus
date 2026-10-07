"""Worker drain helpers for chained MVP (Forge loop + chaos)."""

from __future__ import annotations

import uuid

from core.commands.context import CommandContext
from core.domain.enums import TaskStatus, WorkType
from core.domain.tasks.models import Task
from core.domain.tasks.service import TaskService
from core.repositories.materialization_loop import MaterializationLoop
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.planning_workflow_harness import ensure_system_actor
from tests.journey.chained.chaos_hooks import maybe_chaos_before_worker_round
from tests.journey.feature_change_helpers import (
    drain_workers_factory,
    wait_for_development_tasks_complete,
)


async def drain_until_code_change_tasks_terminal(
    factory: async_sessionmaker[AsyncSession],
    cycle_id: uuid.UUID,
    *,
    correlation_prefix: str,
    max_outer_rounds: int = 90,
    rounds_per_drain: int = 15,
    final_wait_timeout: float = 900.0,
    inject_chaos: bool = False,
) -> None:
    """Drain workers until all CODE_CHANGE tasks on the cycle reach a terminal status."""
    terminal = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}

    for _ in range(max_outer_rounds):
        if inject_chaos:
            async with factory() as session, session.begin():
                actor = await ensure_system_actor(session)
                ctx = CommandContext(actor=actor, correlation_id=f"{correlation_prefix}-chaos")
                await maybe_chaos_before_worker_round(session, ctx, delivery_cycle_id=cycle_id)

        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            mat_ctx = CommandContext(actor=actor, correlation_id=f"{correlation_prefix}-mat")
            await MaterializationLoop().run_once(session, mat_ctx)

        await drain_workers_factory(
            factory,
            correlation_prefix=correlation_prefix,
            rounds=rounds_per_drain,
        )

        async with factory() as session, session.begin():
            await ensure_system_actor(session)
            blocked = list(
                (
                    await session.execute(
                        select(Task).where(
                            Task.delivery_cycle_id == cycle_id,
                            Task.work_type == WorkType.CODE_CHANGE,
                            Task.status == TaskStatus.BLOCKED,
                        )
                    )
                ).scalars()
            )
            task_svc = TaskService()
            for task in blocked:
                await task_svc.on_dependency_completed(session, task.id)

        async with factory() as session:
            pending = list(
                (
                    await session.execute(
                        select(Task).where(
                            Task.delivery_cycle_id == cycle_id,
                            Task.work_type == WorkType.CODE_CHANGE,
                            Task.status.not_in(tuple(terminal)),
                        )
                    )
                ).scalars()
            )
            if not pending:
                break
    else:
        async with factory() as session:
            pending = list(
                (
                    await session.execute(
                        select(Task).where(
                            Task.delivery_cycle_id == cycle_id,
                            Task.work_type == WorkType.CODE_CHANGE,
                            Task.status.not_in(tuple(terminal)),
                        )
                    )
                ).scalars()
            )
        detail = ", ".join(f"{t.id}:{t.status.value}" for t in pending[:12])
        raise TimeoutError(
            f"CODE_CHANGE tasks on cycle {cycle_id} did not finish after {max_outer_rounds} rounds"
            f" ({len(pending)} pending: {detail})"
        )

    await wait_for_development_tasks_complete(factory, cycle_id, timeout=final_wait_timeout)


async def bugfix_drain_with_chaos(
    factory: async_sessionmaker[AsyncSession],
    cycle_id: uuid.UUID,
    *,
    correlation_prefix: str = "mvp-bf",
    rounds: int = 50,
) -> None:
    """Bug-fix worker drain with optional sentinel lease chaos (DC-004)."""
    import os

    for i in range(rounds):
        if os.environ.get("MVP_CHAOS") == "1":
            async with factory() as session, session.begin():
                actor = await ensure_system_actor(session)
                ctx = CommandContext(actor=actor, correlation_id=f"{correlation_prefix}-chaos-{i}")
                await maybe_chaos_before_worker_round(session, ctx, delivery_cycle_id=cycle_id)
        await drain_workers_factory(
            factory, correlation_prefix=f"{correlation_prefix}-{i}", rounds=3
        )
