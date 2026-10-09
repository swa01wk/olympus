"""Worker drain helpers for chained MVP (Forge loop + chaos)."""

from __future__ import annotations

import uuid

from core.commands.context import CommandContext
from core.domain.enums import TaskStatus, WorkType
from core.domain.executions.models import Execution
from core.domain.tasks.models import Task, TaskDependency
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
            detail, pending_count = await _code_change_diagnostics(session, cycle_id)
        raise TimeoutError(
            f"CODE_CHANGE tasks on cycle {cycle_id} did not finish after {max_outer_rounds} rounds"
            f" ({pending_count} pending; all CODE_CHANGE tasks: {detail})"
        )

    await wait_for_development_tasks_complete(factory, cycle_id, timeout=final_wait_timeout)

    async with factory() as session:
        failed = await session.scalar(
            select(Task.id).where(
                Task.delivery_cycle_id == cycle_id,
                Task.work_type == WorkType.CODE_CHANGE,
                Task.status == TaskStatus.FAILED,
            )
        )
        if failed is not None:
            detail, _ = await _code_change_diagnostics(session, cycle_id)
            raise AssertionError(f"CODE_CHANGE task failed on cycle {cycle_id}: {detail}")


async def _code_change_diagnostics(session: AsyncSession, cycle_id: uuid.UUID) -> tuple[str, int]:
    """Status, failure, dependencies and execution traces of every CODE_CHANGE task."""
    terminal = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
    tasks = list(
        (
            await session.execute(
                select(Task).where(
                    Task.delivery_cycle_id == cycle_id,
                    Task.work_type == WorkType.CODE_CHANGE,
                )
            )
        ).scalars()
    )
    deps = list(
        (
            await session.execute(
                select(TaskDependency).where(TaskDependency.task_id.in_([t.id for t in tasks]))
            )
        ).scalars()
    )
    failed_execs = list(
        (
            await session.execute(
                select(Execution)
                .where(
                    Execution.task_id.in_([t.id for t in tasks if t.status == TaskStatus.FAILED])
                )
                .order_by(Execution.created_at)
            )
        ).scalars()
    )
    failures = {e.task_id: f"{e.failure_class}: {e.failure_detail}" for e in failed_execs}
    traces = [await _execution_trace(session, e) for e in failed_execs]
    for t in tasks:
        if t.status == TaskStatus.READY:
            traces.append(f" {t.key} READY: {await _admission_verdict(session, t)}")
    pending = [t for t in tasks if t.status not in terminal]
    detail = "; ".join(
        f"{t.key}:{t.status.value}"
        + (f" last_failure={failures[t.id]!r}" if t.id in failures else "")
        + (f" blocked_reason={t.blocked_reason!r}" if t.blocked_reason else "")
        + (
            f" depends_on={[d.depends_on_task_id for d in deps if d.task_id == t.id]}"
            if any(d.task_id == t.id for d in deps)
            else ""
        )
        for t in tasks
    )
    detail += f"; ids: { {t.key: t.id for t in tasks} }; failed executions:\n" + "\n".join(traces)
    return detail, len(pending)


async def _admission_verdict(session: AsyncSession, task: Task) -> str:
    """Why admission skips a READY task; the caller's session is never committed."""
    from core.domain.exceptions import DomainError
    from core.scheduler.admission import AdmissionService

    actor = await ensure_system_actor(session)
    try:
        row = await AdmissionService().admit_task(
            session, task.id, CommandContext(actor=actor, correlation_id="drain-diagnostics")
        )
    except DomainError as exc:
        return f"{exc.code} {exc.details or exc.message}"
    return f"admittable now (execution {row.key}); contract={task.current_contract_id}"


async def _execution_trace(session: AsyncSession, execution: Execution) -> str:
    """Model-call count and ToolGateway calls of one execution, oldest first."""
    from core.domain.actions.models import ActionRequest, ActionResult
    from core.domain.model_calls.models import ModelCall
    from sqlalchemy import func

    calls = await session.scalar(
        select(func.count()).select_from(ModelCall).where(ModelCall.execution_id == execution.id)
    )
    rows = (
        await session.execute(
            select(ActionRequest, ActionResult)
            .join(ActionResult, ActionResult.action_request_id == ActionRequest.id, isouter=True)
            .where(ActionRequest.execution_id == execution.id)
            .order_by(ActionRequest.created_at)
        )
    ).all()
    lines = [
        f"  {req.tool} {str(req.params)[:160]} -> {req.status.value}"
        + (f" {res.status} {res.error_class}: {(res.error_detail or '')[:200]}" if res else "")
        for req, res in rows
    ]
    failed_calls = (
        await session.scalars(
            select(ModelCall)
            .where(ModelCall.execution_id == execution.id, ModelCall.validation_errors.is_not(None))
            .order_by(ModelCall.created_at)
        )
    ).all()
    lines += [
        f"  model {mc.purpose} {mc.status}: {str(mc.validation_errors)[:600]}"
        for mc in failed_calls
    ]
    return (
        f" execution {execution.key} attempt {execution.attempt_number} "
        f"{execution.status.value} model_calls={calls} tools={len(rows)}\n" + "\n".join(lines)
    )


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
