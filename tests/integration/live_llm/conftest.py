from __future__ import annotations

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from apps.control_api.main import create_app
from core.config.settings import OlympusSettings, clear_settings_cache, get_settings
from core.db.engine import dispose_engine
from core.domain.actors.models import Actor, ApiToken
from core.domain.actors.tokens import generate_token, hash_token
from core.domain.enums import ActorKind, ActorRole
from core.runtime.budget import get_budget_ledger
from core.runtime.model_policy import clear_models_config_cache
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

LIVE_OPENAI_MODEL = "gpt-5.4-mini"


@pytest.fixture(autouse=True)
def _reset_live_llm_budget_per_test() -> Iterator[None]:
    get_budget_ledger().reset_session()
    yield
    get_budget_ledger().reset_session()


@pytest.fixture(autouse=True)
def _live_openai_model_env() -> Iterator[None]:
    """When OPENAI_API_KEY is present, default live lane to OpenAI gpt-5.4-mini."""
    if not get_settings().openai_api_key.get_secret_value():
        yield
        return
    os.environ["MODEL_PROVIDER"] = "openai"
    os.environ.setdefault("MODEL_DEFAULT", LIVE_OPENAI_MODEL)
    os.environ.setdefault("MODEL_VERIFICATION", LIVE_OPENAI_MODEL)
    clear_settings_cache()
    clear_models_config_cache()
    yield
    clear_settings_cache()
    clear_models_config_cache()


@pytest.fixture
async def operator_token(async_engine) -> str:
    token = generate_token()
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        actor = Actor(
            kind=ActorKind.HUMAN,
            name=f"live-operator-{uuid4().hex[:8]}",
            roles=[ActorRole.OPERATOR.value, ActorRole.APPROVER.value],
        )
        session.add(actor)
        await session.flush()
        session.add(ApiToken(actor_id=actor.id, token_hash=hash_token(token)))
    return token


@pytest.fixture
async def control_app(
    async_engine,
    postgres_url: str,
    tmp_path,
) -> FastAPI:
    await dispose_engine()
    settings = OlympusSettings(
        database_url=postgres_url,
        olympus_workspace_root=tmp_path / "ws",
        olympus_storage_root=tmp_path / "storage",
        olympus_env="test",
    )
    session_factory = async_sessionmaker(
        bind=async_engine, class_=AsyncSession, expire_on_commit=False
    )
    app = create_app(settings=settings)
    app.state.session_factory = session_factory
    return app


@pytest.fixture
async def system_actor(db_session: AsyncSession) -> Actor:
    actor = Actor(kind=ActorKind.SYSTEM, name="live-llm-system", roles=[ActorRole.SYSTEM.value])
    db_session.add(actor)
    await db_session.flush()
    return actor
