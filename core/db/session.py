from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.db.engine import get_engine

_session_factory: async_sessionmaker[AsyncSession] | None = None


def create_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    return create_session_factory()


def reset_session_factory() -> None:
    global _session_factory
    _session_factory = None
