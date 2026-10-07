from __future__ import annotations

import os

import pytest
from core.config.settings import clear_settings_cache
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind, ActorRole
from core.runtime.budget import get_budget_ledger
from core.runtime.model_policy import clear_models_config_cache
from core.runtime.model_router import ModelRouter
from core.runtime.providers.fake_provider import FakeProvider
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(autouse=True)
def _runtime_env() -> None:
    # FakeProvider is registered under the "anthropic" provider key in unit tests.
    os.environ["MODEL_PROVIDER"] = "anthropic"
    os.environ["MODEL_DEFAULT"] = "claude-3-5-haiku-20241022"
    os.environ["MODEL_VERIFICATION"] = "claude-3-5-haiku-20241022"
    clear_settings_cache()
    clear_models_config_cache()
    get_budget_ledger().reset_session()
    yield
    get_budget_ledger().reset_session()


@pytest.fixture
async def system_actor(db_session: AsyncSession) -> Actor:
    actor = Actor(kind=ActorKind.SYSTEM, name="runtime-system", roles=[ActorRole.SYSTEM.value])
    db_session.add(actor)
    await db_session.flush()
    return actor


@pytest.fixture
def fake_provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
async def model_router(db_session, system_actor, fake_provider: FakeProvider) -> ModelRouter:
    return ModelRouter(
        db_session,
        actor_id=system_actor.id,
        providers={"anthropic": fake_provider},
    )
