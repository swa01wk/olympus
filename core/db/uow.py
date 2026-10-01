from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.db.session import get_async_session_factory


@asynccontextmanager
async def unit_of_work(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> AsyncIterator[AsyncSession]:
    factory = session_factory or get_async_session_factory()
    async with factory() as session, session.begin():
        yield session
