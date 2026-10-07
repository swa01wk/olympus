"""Workflow integration (Phase 08 §15) — IC precursor to Phase 10."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from core.config.settings import clear_settings_cache, get_settings
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind, ActorRole
from core.runtime.model_policy import clear_models_config_cache
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.integration.conftest import system_actor, system_ctx  # noqa: F401

LIVE_OPENAI_MODEL = "gpt-5.4-mini"


@pytest.fixture(autouse=True)
async def _seed_agent_actor_for_tool_gateway(db_session: AsyncSession) -> None:
    """ToolGateway attributes mutating tool calls to an AGENT actor (Phase 04 parity)."""
    existing = await db_session.execute(
        select(Actor.id).where(Actor.kind == ActorKind.AGENT).limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return
    db_session.add(
        Actor(
            kind=ActorKind.AGENT,
            name="workflow-integration-agent",
            roles=[ActorRole.SYSTEM.value],
        )
    )
    await db_session.flush()


@pytest.fixture(autouse=True)
def _live_openai_model_env(request: pytest.FixtureRequest) -> Iterator[None]:
    """When OPENAI_API_KEY is present, default live workflow IC tests to OpenAI."""
    if "live_llm" not in request.keywords:
        yield
        return
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
