from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.approvals.models import Approval
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ApprovalStatus, ApprovalType, SpecStatus
from core.intelligence.impact.enums import ImpactAssessmentStatus, SpecDeltaStatus
from core.intelligence.impact.models import ImpactAssessment, SpecDelta
from core.planning.models import Architecture
from core.state.guards import GuardResult


async def impact_assessment_complete(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> GuardResult:
    ia = (
        await session.execute(
            select(ImpactAssessment)
            .where(
                ImpactAssessment.delivery_cycle_id == cycle.id,
                ImpactAssessment.status == ImpactAssessmentStatus.COMPLETE.value,
            )
            .order_by(ImpactAssessment.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if ia is None:
        return GuardResult(ok=False, reasons=("IMPACT_ASSESSMENT_MISSING",))
    if ia.spec_delta_id is None:
        return GuardResult(ok=True)
    approved_delta = (
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
    if approved_delta is None:
        return GuardResult(ok=False, reasons=("SPEC_DELTA_NOT_APPROVED",))
    if ia.spec_delta_id != approved_delta.id:
        return GuardResult(ok=False, reasons=("IMPACT_SPEC_DELTA_STALE",))
    delta = await session.get(SpecDelta, ia.spec_delta_id)
    if delta is None or delta.content_hash != approved_delta.content_hash:
        return GuardResult(ok=False, reasons=("SPEC_DELTA_HASH_MISMATCH",))
    return GuardResult(ok=True)


async def architecture_delta_resolved(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> GuardResult:
    ia = (
        await session.execute(
            select(ImpactAssessment)
            .where(
                ImpactAssessment.delivery_cycle_id == cycle.id,
                ImpactAssessment.status == ImpactAssessmentStatus.COMPLETE.value,
            )
            .order_by(ImpactAssessment.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if ia is None or not ia.architecture_delta_suggested:
        return GuardResult(ok=True)

    arch_delta = (
        await session.execute(
            select(Architecture)
            .where(
                Architecture.project_id == cycle.project_id,
                Architecture.kind == "DELTA",
                Architecture.status == SpecStatus.APPROVED,
            )
            .order_by(Architecture.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if arch_delta is not None:
        return GuardResult(ok=True)

    declined = (
        await session.execute(
            select(Approval)
            .where(
                Approval.project_id == cycle.project_id,
                Approval.delivery_cycle_id == cycle.id,
                Approval.approval_type == ApprovalType.ARCHITECTURE_DELTA,
                Approval.status == ApprovalStatus.APPROVED,
            )
            .order_by(Approval.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if declined is not None:
        return GuardResult(ok=True)
    return GuardResult(ok=False, reasons=("ARCHITECTURE_DELTA_UNRESOLVED",))
