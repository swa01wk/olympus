"""Journey test harness (Phase 10 Greenfield)."""

from __future__ import annotations

import pytest
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind, ActorRole
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from tests.workflow.product_model.conftest import control_app, operator_token  # noqa: F401

pytestmark = [pytest.mark.journey]


@pytest.fixture(autouse=True)
async def _seed_agent_actor_for_tool_gateway(async_engine: AsyncEngine) -> None:
    """ToolGateway attributes Forge's mutating tool calls to an AGENT actor."""
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        existing = await session.execute(
            select(Actor.id).where(Actor.kind == ActorKind.AGENT).limit(1)
        )
        if existing.scalar_one_or_none() is None:
            session.add(
                Actor(
                    kind=ActorKind.AGENT,
                    name="journey-agent",
                    roles=[ActorRole.SYSTEM.value],
                )
            )
