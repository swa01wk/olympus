from __future__ import annotations

import asyncio

import pytest
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import ActorKind, ActorRole, DeliveryCycleType
from core.domain.exceptions import StateConflict
from core.domain.projects.models import Project
from core.state.transition_service import TransitionService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_concurrent_cancel_one_wins(async_engine) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as setup, setup.begin():
        actor = Actor(
            kind=ActorKind.HUMAN,
            name="conc",
            roles=[ActorRole.OPERATOR.value],
        )
        setup.add(actor)
        project = Project(key="conc-p", name="Conc")
        setup.add(project)
        await setup.flush()
        ctx = CommandContext(actor=actor, correlation_id="conc")
        cycle = await DeliveryCycleService().create(
            setup, project.id, DeliveryCycleType.GREENFIELD_BUILD, "o", ctx
        )
        cycle_id = cycle.id
        state = cycle.state
        actor_id = actor.id

    async def attempt() -> str | None:
        async with factory() as session, session.begin():
            actor_row = await session.get(Actor, actor_id)
            assert actor_row is not None
            ctx = CommandContext(actor=actor_row, correlation_id="conc-attempt")
            try:
                await TransitionService().transition(
                    session,
                    "delivery_cycle",
                    cycle_id,
                    state,
                    "cancel",
                    ctx,
                )
                return "ok"
            except StateConflict:
                return "conflict"

    results = await asyncio.gather(attempt(), attempt())
    assert results.count("ok") == 1
    assert results.count("conflict") == 1
