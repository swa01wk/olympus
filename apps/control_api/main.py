from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from core.config.settings import OlympusSettings, get_settings
from core.db.engine import create_async_engine_from_settings, dispose_engine
from core.db.session import create_session_factory, reset_session_factory
from core.observability.logging import configure_logging
from fastapi import FastAPI

from apps.control_api.middleware import CorrelationIdMiddleware
from apps.control_api.routers import health


def _resolve_settings(app: FastAPI) -> OlympusSettings:
    override: OlympusSettings | None = getattr(app.state, "settings_override", None)
    if override is not None:
        return override
    return get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = _resolve_settings(app)
    configure_logging(settings)
    engine = create_async_engine_from_settings(settings)
    create_session_factory()
    app.state.settings = settings
    app.state.engine = engine
    yield
    await dispose_engine()
    reset_session_factory()


def create_app(settings: OlympusSettings | None = None) -> FastAPI:
    app = FastAPI(title="Olympus Control API", lifespan=lifespan)
    app.state.settings_override = settings
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(health.router)
    return app


app = create_app()
