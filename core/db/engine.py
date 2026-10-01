from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from core.config.settings import OlympusSettings

_engine: AsyncEngine | None = None
_engine_url: str | None = None


def create_async_engine_from_settings(settings: OlympusSettings) -> AsyncEngine:
    global _engine, _engine_url
    url = settings.database_url
    if _engine is not None and _engine_url == url:
        return _engine
    if _engine is not None:
        raise RuntimeError("Async engine already created for a different DATABASE_URL")
    _engine_url = url
    _engine = create_async_engine(
        url,
        pool_pre_ping=True,
        echo=False,
    )
    return _engine


def get_engine() -> AsyncEngine:
    if _engine is None:
        from core.config.settings import get_settings

        return create_async_engine_from_settings(get_settings())
    return _engine


async def dispose_engine() -> None:
    global _engine, _engine_url
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _engine_url = None
