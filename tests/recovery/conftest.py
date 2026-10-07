from __future__ import annotations

import os

import pytest
from core.commands.context import CommandContext
from core.config.settings import clear_settings_cache
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind, ActorRole
from core.domain.projects.models import Project
from core.runtime.budget import get_budget_ledger
from core.runtime.model_policy import clear_models_config_cache
from core.runtime.model_router import ModelRouter
from core.runtime.providers.fake_provider import FakeProvider
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(autouse=True)
def _recovery_runtime_env() -> None:
    os.environ["MODEL_PROVIDER"] = "anthropic"
    os.environ["MODEL_DEFAULT"] = "claude-3-5-haiku-20241022"
    clear_settings_cache()
    clear_models_config_cache()
    get_budget_ledger().reset_session()
    yield
    get_budget_ledger().reset_session()


@pytest.fixture
async def system_actor(db_session: AsyncSession) -> Actor:
    actor = Actor(kind=ActorKind.SYSTEM, name="recovery-system", roles=[ActorRole.SYSTEM.value])
    db_session.add(actor)
    await db_session.flush()
    return actor


@pytest.fixture
def system_ctx(system_actor: Actor) -> CommandContext:
    return CommandContext(actor=system_actor, correlation_id="recovery-system")


@pytest.fixture
async def sample_project(db_session: AsyncSession) -> Project:
    project = Project(key="recovery-proj", name="Recovery")
    db_session.add(project)
    await db_session.flush()
    return project


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
