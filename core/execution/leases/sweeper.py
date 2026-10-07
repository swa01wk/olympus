from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.enums import ExecutionStatus, LeaseState
from core.domain.events.append import append_domain_event
from core.domain.executions.models import Execution, ExecutionLease
from core.domain.tasks.models import Task
from core.execution.service import ExecutionService
from core.state.transition_service import TransitionService


class LeaseSweeper:
    def __init__(
        self,
        *,
        executions: ExecutionService | None = None,
        transitions: TransitionService | None = None,
    ) -> None:
        self._executions = executions or ExecutionService()
        self._transitions = transitions or TransitionService()

    async def sweep_expired(self, session: AsyncSession, ctx: CommandContext) -> int:
        now = datetime.now(UTC)
        result = await session.execute(
            select(ExecutionLease).where(
                ExecutionLease.state == LeaseState.ACTIVE,
                ExecutionLease.expires_at < now,
            )
        )
        count = 0
        for lease in result.scalars():
            await self._recover_lease(session, lease, ctx)
            count += 1
        return count

    async def _recover_lease(
        self,
        session: AsyncSession,
        lease: ExecutionLease,
        ctx: CommandContext,
    ) -> None:
        lease.state = LeaseState.EXPIRED
        execution = await session.get(Execution, lease.execution_id)
        if execution is None:
            return
        await append_domain_event(
            session,
            aggregate_type="execution",
            aggregate_id=execution.id,
            event_type="lease.expired",
            payload={"lease_id": str(lease.id), "worker_id": lease.worker_id},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            delivery_cycle_id=execution.delivery_cycle_id,
        )
        if execution.status == ExecutionStatus.LEASED:
            execution.lease_attempts += 1
            await self._executions.transition(
                session,
                execution.id,
                "requeue",
                ctx,
                payload={"failure_class": "LEASE_EXPIRED"},
            )
        elif execution.status in {
            ExecutionStatus.STARTED,
            ExecutionStatus.OUTPUT_PRODUCED,
            ExecutionStatus.VALIDATING,
        }:
            task = await session.get(Task, execution.task_id)
            await self._executions.transition(
                session,
                execution.id,
                "fail",
                ctx,
                payload={
                    "failure_class": "LEASE_EXPIRED",
                    "retriable": True,
                },
            )
            await session.refresh(execution)
            if task:
                await self._executions.sync_task_on_failure(session, execution, task, ctx)
