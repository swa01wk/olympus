from __future__ import annotations

import pytest
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind, ActorRole
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def system_actor(db_session: AsyncSession) -> Actor:
    actor = Actor(kind=ActorKind.SYSTEM, name="security-system", roles=[ActorRole.SYSTEM.value])
    db_session.add(actor)
    await db_session.flush()
    return actor


@pytest.fixture
def system_ctx(system_actor: Actor) -> CommandContext:
    return CommandContext(actor=system_actor, correlation_id="security-test")
