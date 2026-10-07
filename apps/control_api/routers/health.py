from __future__ import annotations

import json
from importlib.metadata import version
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from core.config.settings import get_settings
from core.execution.sandbox.runner import sandbox_available
from fastapi import APIRouter, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

router = APIRouter(tags=["health"])
_ALEMBIC_INI = str(Path(__file__).resolve().parents[3] / "alembic.ini")


def _package_version() -> str:
    try:
        return version("olympus")
    except Exception:
        return "0.0.0"


async def _db_ok(engine: AsyncEngine) -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _migrations_at_head(engine: AsyncEngine, alembic_ini: str = _ALEMBIC_INI) -> bool:
    try:
        config = Config(alembic_ini)
        script = ScriptDirectory.from_config(config)
        head = script.get_current_head()
        if head is None:
            return True
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            current = result.scalar_one_or_none()
        return current == head
    except Exception:
        return False


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": _package_version()}


@router.get("/ready")
async def ready(request: Request) -> Response:
    engine: AsyncEngine = request.app.state.engine
    settings = get_settings()
    db_ok = await _db_ok(engine)
    migrations_ok = await _migrations_at_head(engine) if db_ok else False
    storage_ok = settings.olympus_storage_root.is_dir()
    sandbox_ok = sandbox_available(settings)
    llm_ok = True
    if settings.llm_live_tests:
        provider = settings.model_provider
        if provider == "anthropic" and not settings.anthropic_api_key.get_secret_value():
            llm_ok = False
        if provider == "openai" and not settings.openai_api_key.get_secret_value():
            llm_ok = False

    ready = db_ok and migrations_ok and storage_ok and sandbox_ok and llm_ok
    if ready:
        return Response(
            content='{"db":"ok","migrations":"head","storage":"ok","sandbox":"ok"}',
            media_type="application/json",
            status_code=200,
        )

    body = {
        "db": "ok" if db_ok else "error",
        "migrations": "head" if migrations_ok else "error",
        "storage": "ok" if storage_ok else "error",
        "sandbox": "ok" if sandbox_ok else "error",
        "llm_credentials": "ok" if llm_ok else "error",
    }
    return Response(
        content=json.dumps(body),
        media_type="application/json",
        status_code=503,
    )
