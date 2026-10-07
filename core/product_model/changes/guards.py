from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import DeliveryCycleType, ProjectReadiness
from core.domain.projects.models import Project
from core.intelligence.baselines.models import BaselineSet
from core.product_model.changes.models import ChangeRequest
from core.release.enums import ReleaseStatus
from core.release.models import Release
from core.state.guards import GuardResult


async def change_request_linked(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> GuardResult:
    if cycle.type != DeliveryCycleType.FEATURE_CHANGE:
        return GuardResult(ok=False, reasons=("NOT_FEATURE_CHANGE_CYCLE",))
    cr = (
        await session.execute(
            select(ChangeRequest).where(ChangeRequest.delivery_cycle_id == cycle.id)
        )
    ).scalar_one_or_none()
    if cr is None:
        return GuardResult(ok=False, reasons=("CHANGE_REQUEST_NOT_LINKED",))
    if cr.status not in {"RECEIVED", "INTERPRETED", "SPEC_APPROVED", "IN_DELIVERY"}:
        return GuardResult(ok=False, reasons=(f"CHANGE_REQUEST_STATUS:{cr.status}",))
    return GuardResult(ok=True)


async def project_change_ready(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> GuardResult:
    project = await session.get(Project, cycle.project_id)
    if project is None:
        return GuardResult(ok=False, reasons=("PROJECT_NOT_FOUND",))
    if project.readiness_state == ProjectReadiness.READY_FOR_CHANGE:
        return GuardResult(ok=True)
    released_gf = (
        await session.execute(
            select(Release)
            .join(DeliveryCycle, Release.delivery_cycle_id == DeliveryCycle.id)
            .where(
                Release.project_id == cycle.project_id,
                Release.status == ReleaseStatus.RELEASED,
                DeliveryCycle.type == DeliveryCycleType.GREENFIELD_BUILD,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if released_gf is None:
        return GuardResult(ok=False, reasons=("PROJECT_NOT_READY_FOR_CHANGE",))
    if project.active_baseline_set_id is None:
        return GuardResult(ok=False, reasons=("ACTIVE_BASELINE_SET_MISSING",))
    bset = await session.get(BaselineSet, project.active_baseline_set_id)
    if bset is None:
        return GuardResult(ok=False, reasons=("ACTIVE_BASELINE_SET_MISSING",))
    return GuardResult(ok=True)
