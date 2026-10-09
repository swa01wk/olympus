from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import DeliveryCycleType
from core.domain.repositories.models import Repository
from core.integration.enums import ICStatus
from core.integration.models import IntegrationCandidate
from core.intelligence.baselines.enums import BaselineStatus, ReadinessResult
from core.intelligence.baselines.models import (
    BehavioralBaseline,
    PromotionDecision,
    ReadinessAssessment,
)
from core.intelligence.baselines.readiness import _review_subjects
from core.state.guards import GuardResult


async def baseline_review_complete(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> GuardResult:
    if cycle.type != DeliveryCycleType.BROWNFIELD_ONBOARDING:
        return GuardResult(ok=True)
    subjects = await _review_subjects(session, cycle)
    if not subjects:
        any_decision = (
            (
                await session.execute(
                    select(PromotionDecision.id).where(
                        PromotionDecision.delivery_cycle_id == cycle.id
                    )
                )
            )
            .scalars()
            .first()
        )
        if any_decision is not None:
            return GuardResult(ok=True)
        return GuardResult(ok=False, reasons=("REVIEW_QUEUE_EMPTY",))
    decided = (
        (
            await session.execute(
                select(PromotionDecision.subject_id).where(
                    PromotionDecision.delivery_cycle_id == cycle.id
                )
            )
        )
        .scalars()
        .all()
    )
    decided_set = set(decided)
    pending = [sid for sid in subjects if sid not in decided_set]
    if pending:
        return GuardResult(ok=False, reasons=(f"REVIEW_PENDING:{len(pending)}",))
    unresolved_baselines = (
        (
            await session.execute(
                select(BehavioralBaseline.id).where(
                    BehavioralBaseline.project_id == cycle.project_id,
                    BehavioralBaseline.status == BaselineStatus.PROPOSED,
                )
            )
        )
        .scalars()
        .all()
    )
    if unresolved_baselines:
        return GuardResult(ok=False, reasons=("BASELINE_PROPOSALS_PENDING",))
    return GuardResult(ok=True)


async def readiness_failed_remediable(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> GuardResult:
    row = (
        await session.execute(
            select(ReadinessAssessment)
            .where(ReadinessAssessment.delivery_cycle_id == cycle.id)
            .order_by(ReadinessAssessment.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        return GuardResult(ok=False, reasons=("READINESS_ASSESSMENT_MISSING",))
    if row.result == ReadinessResult.READY:
        return GuardResult(ok=False, reasons=("READINESS_ALREADY_READY",))
    if not row.remediable:
        return GuardResult(ok=False, reasons=("READINESS_NOT_REMEDIABLE",))
    return GuardResult(ok=True)


async def remediation_integrated_and_reindexed(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> GuardResult:
    ic = (
        await session.execute(
            select(IntegrationCandidate)
            .where(
                IntegrationCandidate.delivery_cycle_id == cycle.id,
                IntegrationCandidate.status == ICStatus.READY,
            )
            .order_by(IntegrationCandidate.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if ic is None or ic.integrated_sha is None:
        return GuardResult(ok=False, reasons=("REMEDIATION_IC_NOT_READY",))
    if cycle.repository_id is None:
        return GuardResult(ok=False, reasons=("REPOSITORY_MISSING",))
    repo = await session.get(Repository, cycle.repository_id)
    if repo is None:
        return GuardResult(ok=False, reasons=("REPOSITORY_MISSING",))
    if repo.canonical_commit != ic.integrated_sha:
        return GuardResult(ok=False, reasons=("CANONICAL_SHA_MISMATCH",))
    if repo.released_commit is not None and repo.released_commit != ic.integrated_sha:
        return GuardResult(ok=False, reasons=("RELEASED_SHA_MISMATCH",))
    return GuardResult(ok=True)


async def readiness_assessment_ready(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> GuardResult:
    row = (
        await session.execute(
            select(ReadinessAssessment)
            .where(ReadinessAssessment.delivery_cycle_id == cycle.id)
            .order_by(ReadinessAssessment.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        return GuardResult(ok=False, reasons=("READINESS_ASSESSMENT_MISSING",))
    if row.result != ReadinessResult.READY:
        return GuardResult(ok=False, reasons=("READINESS_NOT_READY",))
    if cycle.repository_id is None:
        return GuardResult(ok=False, reasons=("REPOSITORY_MISSING",))
    repo = await session.get(Repository, cycle.repository_id)
    if repo is None or repo.canonical_commit is None:
        return GuardResult(ok=False, reasons=("CANONICAL_COMMIT_MISSING",))
    if row.commit_sha != repo.canonical_commit:
        return GuardResult(ok=False, reasons=("READINESS_STALE_SHA",))
    active = (
        (
            await session.execute(
                select(BehavioralBaseline).where(
                    BehavioralBaseline.project_id == cycle.project_id,
                    BehavioralBaseline.status == BaselineStatus.ACTIVE,
                )
            )
        )
        .scalars()
        .all()
    )
    if not active:
        return GuardResult(ok=False, reasons=("NO_ACTIVE_BASELINES",))
    for bl in active:
        if bl.established_sha != repo.canonical_commit:
            return GuardResult(ok=False, reasons=("BASELINE_SHA_DRIFT",))
    return GuardResult(ok=True)
