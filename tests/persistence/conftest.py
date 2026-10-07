from __future__ import annotations

import pytest
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind, ActorRole
from core.domain.projects.models import Project
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def operator_actor(db_session: AsyncSession) -> Actor:
    actor = Actor(
        kind=ActorKind.HUMAN,
        name="persist-operator",
        roles=[ActorRole.OPERATOR.value, ActorRole.APPROVER.value],
    )
    db_session.add(actor)
    await db_session.flush()
    return actor


@pytest.fixture
def operator_ctx(operator_actor: Actor) -> CommandContext:
    return CommandContext(actor=operator_actor, correlation_id="persist-test")


@pytest.fixture
async def system_actor(db_session: AsyncSession) -> Actor:
    actor = Actor(kind=ActorKind.SYSTEM, name="persist-system", roles=[ActorRole.SYSTEM.value])
    db_session.add(actor)
    await db_session.flush()
    return actor


@pytest.fixture
def system_ctx(system_actor: Actor) -> CommandContext:
    return CommandContext(actor=system_actor, correlation_id="persist-system")


@pytest.fixture
async def sample_project(db_session: AsyncSession) -> Project:
    project = Project(key="persist-proj", name="Persist")
    db_session.add(project)
    await db_session.flush()
    return project
