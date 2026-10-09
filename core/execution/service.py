from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.enums import ExecutionStatus, LeaseState, TaskStatus
from core.domain.events.append import append_domain_event
from core.domain.exceptions import IllegalTransition, Unauthorized
from core.domain.executions.models import Execution, ExecutionEvent, ExecutionLease
from core.state.machines import EXECUTION_MACHINE
from core.state.transition_service import TransitionService


class ExecutionService:
    def __init__(self, transitions: TransitionService | None = None) -> None:
        self.transitions = transitions or TransitionService()

    async def transition(
        self,
        session: AsyncSession,
        execution_id: uuid.UUID,
        command: str,
        ctx: CommandContext,
        *,
        lease_id: uuid.UUID | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Execution:
        result = await session.execute(
            select(Execution).where(Execution.id == execution_id).with_for_update()
        )
        execution = result.scalar_one_or_none()
        if execution is None:
            raise ValueError("execution not found")
        current = execution.status.value
        edge = EXECUTION_MACHINE.edge(current, command)
        if edge is None:
            raise IllegalTransition(aggregate="execution", state=current, command=command)
        if ctx.actor.kind not in edge.actor_kinds:
            raise Unauthorized(f"Actor kind {ctx.actor.kind} not permitted for execution")
        if lease_id is not None:
            await self._assert_active_lease(session, execution_id, lease_id)
        before = execution.status.value
        execution.status = ExecutionStatus(edge.to)
        if command == "start" and execution.started_at is None:
            execution.started_at = datetime.now(UTC)
        if edge.to in {s.value for s in ExecutionService._terminal()}:
            execution.finished_at = datetime.now(UTC)
        if payload:
            if "failure_class" in payload:
                execution.failure_class = str(payload["failure_class"])
            if "failure_detail" in payload:
                execution.failure_detail = payload["failure_detail"]
            if "retriable" in payload:
                execution.retriable = bool(payload["retriable"])
            if "output" in payload:
                execution.output = payload["output"]
            if "runtime_metadata" in payload:
                execution.runtime_metadata = payload["runtime_metadata"]
        await session.flush()
        await self._append_execution_event(session, execution.id, f"execution.{command}", payload)
        await append_domain_event(
            session,
            aggregate_type="execution",
            aggregate_id=execution.id,
            event_type=f"execution.{edge.to.lower()}",
            payload={"from": before, "to": edge.to, "command": command},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            delivery_cycle_id=execution.delivery_cycle_id,
        )
        return execution

    async def _assert_active_lease(
        self,
        session: AsyncSession,
        execution_id: uuid.UUID,
        lease_id: uuid.UUID,
    ) -> ExecutionLease:
        lease = await session.get(ExecutionLease, lease_id)
        if lease is None or lease.execution_id != execution_id:
            raise Unauthorized("Invalid lease")
        if lease.state != LeaseState.ACTIVE:
            raise Unauthorized("Lease not active")
        now = await session.scalar(select(func.now()))
        if now and lease.expires_at < now:
            raise Unauthorized("Lease expired")
        return lease

    async def _append_execution_event(
        self,
        session: AsyncSession,
        execution_id: uuid.UUID,
        event_type: str,
        payload: dict[str, Any] | None,
    ) -> None:
        seq_result = await session.execute(
            select(func.coalesce(func.max(ExecutionEvent.seq), 0)).where(
                ExecutionEvent.execution_id == execution_id
            )
        )
        seq = int(seq_result.scalar_one()) + 1
        session.add(
            ExecutionEvent(
                execution_id=execution_id,
                seq=seq,
                type=event_type,
                payload=payload or {},
            )
        )

    @staticmethod
    def _terminal() -> frozenset[ExecutionStatus]:
        return frozenset(
            {
                ExecutionStatus.COMPLETED,
                ExecutionStatus.FAILED,
                ExecutionStatus.TIMED_OUT,
                ExecutionStatus.CANCELLED,
                ExecutionStatus.STALE,
            }
        )

    async def sync_task_on_execution_complete(
        self,
        session: AsyncSession,
        execution: Execution,
        ctx: CommandContext,
    ) -> None:
        await self.transitions.transition(
            session,
            "task",
            execution.task_id,
            TaskStatus.RUNNING.value,
            "complete",
            ctx,
        )

    async def sync_task_on_failure(
        self,
        session: AsyncSession,
        execution: Execution,
        task: Any,
        ctx: CommandContext,
    ) -> None:
        from core.domain.tasks.models import Task

        task_row = task if isinstance(task, Task) else await session.get(Task, execution.task_id)
        if task_row is None:
            return
        from_state = task_row.status.value
        if (
            from_state == TaskStatus.QUEUED.value
            and execution.retriable
            and task_row.max_attempts > execution.attempt_number
        ):
            task_row.status = TaskStatus.READY
            return
        if execution.retriable and task_row.max_attempts > execution.attempt_number:
            await self.transitions.transition(
                session,
                "task",
                execution.task_id,
                from_state,
                "fail_retry",
                ctx,
            )
        else:
            await self.transitions.transition(
                session,
                "task",
                execution.task_id,
                from_state,
                "fail_terminal",
                ctx,
            )
            if task_row.title.startswith("Characterize "):
                from core.intelligence.baselines.orchestrator import BaselineOrchestrator

                await BaselineOrchestrator().schedule_execution_if_characterized(
                    session, task_row.delivery_cycle_id, ctx
                )
