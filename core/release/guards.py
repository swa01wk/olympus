"""Delivery-cycle guards for release completion."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.delivery_cycles.models import DeliveryCycle
from core.integration.enums import ICStatus
from core.integration.models import IntegrationCandidate
from core.release.enums import ReleaseStatus
from core.release.models import Release
from core.state.guards import GuardResult


async def release_executed(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> GuardResult:
    ic = await session.execute(
        select(IntegrationCandidate)
        .where(
            IntegrationCandidate.delivery_cycle_id == cycle.id,
            IntegrationCandidate.status == ICStatus.READY,
        )
        .order_by(IntegrationCandidate.created_at.desc())
        .limit(1)
    )
    row = ic.scalar_one_or_none()
    if row is None:
        return GuardResult(ok=False, reasons=("IC_NOT_READY",))
    release = await session.execute(
        select(Release).where(
            Release.delivery_cycle_id == cycle.id,
            Release.integration_candidate_id == row.id,
            Release.status == ReleaseStatus.RELEASED,
        )
    )
    if release.scalar_one_or_none() is None:
        return GuardResult(ok=False, reasons=("RELEASE_NOT_EXECUTED",))
    return GuardResult(ok=True)
