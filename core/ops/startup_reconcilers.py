"""Startup reconcilers — orphan leases, worktrees, stuck ICs, connector actions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.domain.enums import ExecutionStatus, LeaseState
from core.domain.executions.models import Execution, ExecutionLease
from core.observability.logging import get_logger
from core.tools.tokens import revoke_tokens_for_execution

logger = get_logger(__name__)


async def reconcile_orphan_leases(session: AsyncSession) -> int:
    settings = get_settings()
    ttl = timedelta(seconds=settings.execution_lease_ttl_seconds)
    cutoff = datetime.now(UTC).replace(tzinfo=None) - ttl
    result = await session.execute(
        select(ExecutionLease).where(
            ExecutionLease.state == LeaseState.ACTIVE,
            ExecutionLease.expires_at < cutoff,
        )
    )
    count = 0
    for lease in result.scalars():
        lease.state = LeaseState.EXPIRED
        await revoke_tokens_for_execution(session, lease.execution_id)
        execution = await session.get(Execution, lease.execution_id)
        if execution and execution.status == ExecutionStatus.STARTED:
            execution.status = ExecutionStatus.FAILED
            execution.failure_class = "LEASE_EXPIRED"
        count += 1
    if count:
        await session.flush()
        logger.info("startup_reconciler.expired_leases", count=count)
    return count


async def run_startup_reconcilers(session: AsyncSession) -> dict[str, int]:
    return {
        "orphan_leases": await reconcile_orphan_leases(session),
    }
