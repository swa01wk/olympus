from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.domain.events.models import DomainEvent

_outbox_notify = asyncio.Event()


def notify_outbox() -> None:
    _outbox_notify.set()


async def publish_pending(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session, session.begin():
        result = await session.execute(
            select(DomainEvent)
            .where(DomainEvent.published_at.is_(None))
            .order_by(DomainEvent.sequence)
            .limit(100)
        )
        rows = list(result.scalars())
        if not rows:
            return 0
        now = datetime.now(UTC)
        for row in rows:
            row.published_at = now
        return len(rows)


async def outbox_loop(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    poll_interval: float = 1.0,
) -> None:
    while True:
        with suppress(Exception):
            await publish_pending(session_factory)
        try:
            await asyncio.wait_for(_outbox_notify.wait(), timeout=poll_interval)
            _outbox_notify.clear()
        except TimeoutError:
            continue
