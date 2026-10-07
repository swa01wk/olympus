from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from core.config.settings import clear_settings_cache, get_settings
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind, ActorRole
from core.runtime.budget import get_budget_ledger
from core.runtime.model_policy import clear_models_config_cache
from sqlalchemy.ext.asyncio import AsyncSession

LIVE_OPENAI_MODEL = "gpt-5.4-mini"


@pytest.fixture(autouse=True)
def _reset_live_llm_budget() -> Iterator[None]:
    get_budget_ledger().reset_session()
    yield
    get_budget_ledger().reset_session()


@pytest.fixture(autouse=True)
def _live_openai_model_env() -> Iterator[None]:
    if not get_settings().openai_api_key.get_secret_value():
        yield
        return
    os.environ["MODEL_PROVIDER"] = "openai"
    os.environ.setdefault("MODEL_DEFAULT", LIVE_OPENAI_MODEL)
    os.environ.setdefault("MODEL_REPOSITORY_REASONING", LIVE_OPENAI_MODEL)
    os.environ.setdefault("MODEL_IMPLEMENTATION", LIVE_OPENAI_MODEL)
    clear_settings_cache()
    clear_models_config_cache()
    yield
    clear_settings_cache()
    clear_models_config_cache()


@pytest.fixture
async def system_actor(db_session: AsyncSession) -> Actor:
    actor = Actor(kind=ActorKind.SYSTEM, name="p18-live-system", roles=[ActorRole.SYSTEM.value])
    db_session.add(actor)
    await db_session.flush()
    return actor
