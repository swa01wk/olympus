"""Scheduler reconciliation loop."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.enums import RepositoryStatus
from core.domain.integrations.models import ReconciliationItem
from core.domain.repositories.models import Repository
from core.integrations.reconciliation.service import ReconciliationService
from core.repositories.sync import RepositorySyncService


async def run_reconciliation_tick(session: AsyncSession, ctx: CommandContext) -> int:
    now = datetime.now(UTC)
    rows = await session.execute(
        select(ReconciliationItem).where(
            ReconciliationItem.status == "OPEN",
            ReconciliationItem.next_attempt_at <= now,
        )
    )
    svc = ReconciliationService()
    count = 0
    for item in rows.scalars():
        await svc.reconcile_item(session, item.id, ctx)
        count += 1
    return count


async def poll_repositories(session: AsyncSession, ctx: CommandContext) -> int:
    repos = await session.execute(
        select(Repository).where(
            Repository.remote_url.isnot(None),
            Repository.status == RepositoryStatus.READY,
        )
    )
    sync = RepositorySyncService()
    count = 0
    for repo in repos.scalars():
        if repo.last_known_head_sha is None:
            continue
        await sync.sync(session, repo.id, ctx)
        count += 1
    return count
