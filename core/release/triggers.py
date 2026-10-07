"""Event-driven release eligibility recompute hooks."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.release.eligibility import ReleaseEligibilityService
from core.release.service import ReleaseService


async def on_eligibility_trigger(
    session: AsyncSession,
    delivery_cycle_id: uuid.UUID,
    ctx: CommandContext,
    *,
    trigger_event_id: uuid.UUID | None = None,
) -> None:
    await ReleaseEligibilityService().recompute_and_persist(
        session,
        delivery_cycle_id,
        ctx,
        trigger_event_id=trigger_event_id,
    )
    await ReleaseService().maybe_advance_cycle_to_release(session, delivery_cycle_id, ctx)
