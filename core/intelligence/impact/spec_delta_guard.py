from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ApprovalType
from core.intelligence.impact.enums import SpecDeltaStatus
from core.intelligence.impact.models import SpecDelta
from core.state.guards import GuardResult


async def spec_delta_approved(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> GuardResult:
    delta = (
        await session.execute(
            select(SpecDelta)
            .where(
                SpecDelta.delivery_cycle_id == cycle.id,
                SpecDelta.status == SpecDeltaStatus.APPROVED.value,
            )
            .order_by(SpecDelta.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if delta is None:
        return GuardResult(ok=False, reasons=("SPEC_DELTA_NOT_APPROVED",))
    if delta.approval_id is None:
        return GuardResult(ok=False, reasons=("SPEC_DELTA_APPROVAL_MISSING",))
    from core.domain.approvals.service import ApprovalService

    satisfied = await ApprovalService().is_satisfied(
        session,
        ApprovalType.SPEC_DELTA,
        "SPEC_DELTA",
        delta.id,
        delta.content_hash,
    )
    if not satisfied:
        return GuardResult(ok=False, reasons=("SPEC_DELTA_HASH_NOT_PINNED",))
    return GuardResult(ok=True)
