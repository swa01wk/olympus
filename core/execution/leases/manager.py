from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.config.settings import OlympusSettings, get_settings
from core.domain.enums import ExecutionStatus, LeaseState
from core.domain.events.append import append_domain_event
from core.domain.executions.models import Execution, ExecutionLease
from core.execution.service import ExecutionService


class LeaseManager:
    def __init__(
        self,
        *,
        settings: OlympusSettings | None = None,
        execution_service: ExecutionService | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._executions = execution_service or ExecutionService()
        self._ttl = timedelta(seconds=self._settings.execution_lease_ttl_seconds)

    async def claim(
        self,
        session: AsyncSession,
        worker_id: str,
        ctx: CommandContext,
    ) -> ExecutionLease | None:
        result = await session.execute(
            select(Execution)
            .where(Execution.status == ExecutionStatus.QUEUED)
            .order_by(Execution.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        execution = result.scalar_one_or_none()
        if execution is None:
            return None
        now = datetime.now(UTC)
        expires = now + self._ttl
        lease = ExecutionLease(
            execution_id=execution.id,
            worker_id=worker_id,
            acquired_at=now,
            heartbeat_at=now,
            expires_at=expires,
            state=LeaseState.ACTIVE,
        )
        session.add(lease)
        await session.flush()
        await self._executions.transition(
            session,
            execution.id,
            "lease",
            ctx,
            lease_id=lease.id,
        )
        await append_domain_event(
            session,
            aggregate_type="execution",
            aggregate_id=execution.id,
            event_type="execution.leased",
            payload={"worker_id": worker_id, "lease_id": str(lease.id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            delivery_cycle_id=execution.delivery_cycle_id,
        )
        return lease

    async def heartbeat(self, session: AsyncSession, lease: ExecutionLease) -> None:
        result = await session.execute(
            select(ExecutionLease).where(ExecutionLease.id == lease.id).with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None or row.state != LeaseState.ACTIVE:
            raise ValueError("lease not active")
        now = datetime.now(UTC)
        row.heartbeat_at = now
        row.expires_at = now + self._ttl
        await session.flush()

    async def release(self, session: AsyncSession, lease: ExecutionLease) -> None:
        result = await session.execute(
            select(ExecutionLease).where(ExecutionLease.id == lease.id).with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None or row.state != LeaseState.ACTIVE:
            return
        row.state = LeaseState.RELEASED
        row.released_at = datetime.now(UTC)
        await session.flush()
