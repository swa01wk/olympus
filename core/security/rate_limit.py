"""Postgres-backed token-bucket rate limiting."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_DEFAULT_WINDOW_SECONDS = 60


async def check_rate_limit(
    session: AsyncSession,
    *,
    key: str,
    limit: int,
    window_seconds: int = _DEFAULT_WINDOW_SECONDS,
) -> tuple[bool, int]:
    """Returns (allowed, current_count). Uses INSERT … ON CONFLICT to increment."""
    now = datetime.now(UTC)
    epoch = int(now.timestamp())
    window_index = epoch // window_seconds
    window_start = datetime.fromtimestamp(
        window_index * window_seconds,
        tz=UTC,
    ).replace(tzinfo=None)

    result = await session.execute(
        text(
            """
            INSERT INTO rate_limits (key, window_start, count)
            VALUES (:key, :window_start, 1)
            ON CONFLICT (key, window_start)
            DO UPDATE SET count = rate_limits.count + 1
            RETURNING count
            """
        ),
        {"key": key, "window_start": window_start},
    )
    count = int(result.scalar_one())
    return count <= limit, count
