"""Release eligibility recompute hook (Phase 10)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind
from core.release.triggers import on_eligibility_trigger


async def recompute_release_eligibility(
    session: AsyncSession,
    delivery_cycle_id: uuid.UUID,
) -> None:
    actor = (
        await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
    ).scalar_one()
    ctx = CommandContext(actor=actor, correlation_id=f"release-eligibility:{delivery_cycle_id}")
    await on_eligibility_trigger(session, delivery_cycle_id, ctx)
