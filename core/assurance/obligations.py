"""Verification obligation derivation (Phase 09 §4)."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.enums import GateType, ObligationReason, ObligationStatus
from core.assurance.evidence_rules import allowed_evidence_types
from core.assurance.models import VerificationObligation
from core.commands.context import CommandContext
from core.domain.enums import SpecStatus
from core.domain.events.append import append_domain_event
from core.integration.models import IntegrationCandidate
from core.product_model.models import AcceptanceCriterion, FeatureSpec, ScopeSet, ScopeSetItem

ObligationSourceFn = Callable[
    [AsyncSession, IntegrationCandidate, CommandContext],
    Awaitable[list[VerificationObligation]],
]

_SOURCES: list[ObligationSourceFn] = []


def register_obligation_source(fn: ObligationSourceFn) -> None:
    _SOURCES.append(fn)


async def _ac_source(
    session: AsyncSession,
    ic: IntegrationCandidate,
    ctx: CommandContext,
) -> list[VerificationObligation]:
    spec_ids = await _scoped_feature_spec_ids(session, ic.delivery_cycle_id)
    if not spec_ids:
        return []
    acs = await session.execute(
        select(AcceptanceCriterion).where(
            AcceptanceCriterion.feature_spec_id.in_(spec_ids),
        )
    )
    rows: list[VerificationObligation] = []
    for ac in acs.scalars():
        spec = await session.get(FeatureSpec, ac.feature_spec_id)
        required = ac.mandatory
        reason = ObligationReason.AC_MANDATORY if required else ObligationReason.AC_OPTIONAL
        rows.append(
            VerificationObligation(
                delivery_cycle_id=ic.delivery_cycle_id,
                integration_candidate_id=ic.id,
                gate_type=GateType.SENTINEL.value,
                subject_type="AC",
                subject_id=ac.id,
                subject_key=ac.lineage_key,
                required=required,
                allowed_evidence_types=allowed_evidence_types(ac.evidence_requirement),
                reason=reason,
                source_refs=[
                    {
                        "type": "ACCEPTANCE_CRITERION",
                        "id": str(ac.id),
                        "path": f"{spec.lineage_key if spec else 'spec'}/{ac.lineage_key}",
                    }
                ],
                status=ObligationStatus.OPEN,
            )
        )
    return rows


async def _scoped_feature_spec_ids(
    session: AsyncSession,
    delivery_cycle_id: uuid.UUID,
) -> list[uuid.UUID]:
    from core.domain.delivery_cycles.models import DeliveryCycle
    from core.domain.enums import DeliveryCycleType, SpecKind

    cycle = await session.get(DeliveryCycle, delivery_cycle_id)
    if cycle is None:
        return []
    if cycle.type == DeliveryCycleType.BROWNFIELD_ONBOARDING:
        bf_specs = await session.execute(
            select(FeatureSpec.id).where(
                FeatureSpec.project_id == cycle.project_id,
                (
                    (FeatureSpec.spec_kind == SpecKind.CANONICAL)
                    & (FeatureSpec.status == SpecStatus.APPROVED)
                )
                | (
                    (FeatureSpec.spec_kind == SpecKind.RECOVERED)
                    & (FeatureSpec.status.in_((SpecStatus.PROMOTED, SpecStatus.CONFIRMED_EXISTING)))
                ),
            )
        )
        return list(bf_specs.scalars())
    scope = await session.execute(
        select(ScopeSet)
        .where(ScopeSet.delivery_cycle_id == delivery_cycle_id)
        .order_by(ScopeSet.created_at.desc())
        .limit(1)
    )
    scope_set = scope.scalar_one_or_none()
    if scope_set is not None:
        items = await session.execute(
            select(ScopeSetItem).where(ScopeSetItem.scope_set_id == scope_set.id)
        )
        return [item.feature_spec_id for item in items.scalars()]
    specs = await session.execute(
        select(FeatureSpec.id).where(
            FeatureSpec.status == SpecStatus.APPROVED,
            FeatureSpec.project_id == cycle.project_id,
        )
    )
    return list(specs.scalars())


async def _superseded_baseline_note(
    session: AsyncSession,
    cycle_id: uuid.UUID,
) -> tuple[frozenset[uuid.UUID], str | None]:
    from core.product_model.defects.service import DefectService

    return await DefectService().superseded_baseline_ids_for_cycle(session, cycle_id)


async def _impact_baseline_and_test_source(
    session: AsyncSession,
    ic: IntegrationCandidate,
    ctx: CommandContext,
) -> list[VerificationObligation]:
    from core.domain.delivery_cycles.models import DeliveryCycle
    from core.intelligence.impact.engine import ImpactEngine
    from core.intelligence.impact.enums import ImpactItemType
    from core.intelligence.impact.models import ImpactItem

    cycle = await session.get(DeliveryCycle, ic.delivery_cycle_id)
    ia = await ImpactEngine().latest_complete(session, ic.delivery_cycle_id)
    if ia is None or cycle is None:
        return []
    superseded_ids, approval_key = await _superseded_baseline_note(session, cycle.id)
    items = (
        await session.execute(
            select(ImpactItem).where(
                ImpactItem.impact_assessment_id == ia.id,
                ImpactItem.selected_for_verification.is_(True),
            )
        )
    ).scalars()
    rows: list[VerificationObligation] = []
    for item in items:
        if item.item_type == ImpactItemType.TEST.value:
            rows.append(
                VerificationObligation(
                    delivery_cycle_id=ic.delivery_cycle_id,
                    integration_candidate_id=ic.id,
                    gate_type=GateType.SENTINEL.value,
                    subject_type="TEST",
                    subject_id=item.id,
                    subject_key=item.ref,
                    required=True,
                    allowed_evidence_types=["UNIT_TEST", "API_TEST", "INTEGRATION_TEST"],
                    reason=ObligationReason.IMPACT_ASSESSMENT,
                    source_refs=[{"type": "IMPACT_ITEM", "ref": item.ref, "path": item.path}],
                    status=ObligationStatus.OPEN,
                )
            )
        elif item.item_type == ImpactItemType.BASELINE.value:
            from core.intelligence.baselines.models import BehavioralBaseline

            bl = (
                await session.execute(
                    select(BehavioralBaseline).where(
                        BehavioralBaseline.lineage_key == item.ref,
                        BehavioralBaseline.project_id == cycle.project_id,
                    )
                )
            ).scalar_one_or_none()
            if bl is None:
                continue
            if bl.id in superseded_ids:
                rows.append(
                    VerificationObligation(
                        delivery_cycle_id=ic.delivery_cycle_id,
                        integration_candidate_id=ic.id,
                        gate_type=GateType.BASELINE.value,
                        subject_type="BASELINE",
                        subject_id=bl.id,
                        subject_key=bl.lineage_key,
                        required=False,
                        allowed_evidence_types=["UNIT_TEST", "API_TEST", "INTEGRATION_TEST"],
                        reason=ObligationReason.BASELINE_REQUIRED,
                        source_refs=[
                            {
                                "type": "IMPACT_ITEM",
                                "ref": item.ref,
                                "path": item.path,
                                "superseded_by_approved_expected_behavior": approval_key,
                            }
                        ],
                        status=ObligationStatus.OPEN,
                    )
                )
                continue
            required = not bl.provisional
            rows.append(
                VerificationObligation(
                    delivery_cycle_id=ic.delivery_cycle_id,
                    integration_candidate_id=ic.id,
                    gate_type=GateType.BASELINE.value,
                    subject_type="BASELINE",
                    subject_id=bl.id,
                    subject_key=bl.lineage_key,
                    required=required,
                    allowed_evidence_types=["UNIT_TEST", "API_TEST", "INTEGRATION_TEST"],
                    reason=ObligationReason.BASELINE_REQUIRED,
                    source_refs=[{"type": "IMPACT_ITEM", "ref": item.ref, "path": item.path}],
                    status=ObligationStatus.OPEN,
                )
            )
    return rows


async def _ac_revalidation_source(
    session: AsyncSession,
    ic: IntegrationCandidate,
    ctx: CommandContext,
) -> list[VerificationObligation]:
    from core.domain.delivery_cycles.models import DeliveryCycle
    from core.domain.enums import DeliveryCycleType
    from core.intelligence.impact.models import ImpactItem
    from core.product_model.models import AcceptanceCriterion

    cycle = await session.get(DeliveryCycle, ic.delivery_cycle_id)
    if cycle is None or cycle.type != DeliveryCycleType.FEATURE_CHANGE:
        return []
    from core.intelligence.impact.engine import ImpactEngine

    ia = await ImpactEngine().latest_complete(session, cycle.id)
    if ia is None:
        return []
    changed_refs = {
        i.ref
        for i in (
            await session.execute(
                select(ImpactItem).where(ImpactItem.impact_assessment_id == ia.id)
            )
        ).scalars()
        if i.path
    }
    if not changed_refs:
        return []
    spec_ids = await _scoped_feature_spec_ids(session, ic.delivery_cycle_id)
    acs = (
        await session.execute(
            select(AcceptanceCriterion).where(
                AcceptanceCriterion.feature_spec_id.in_(spec_ids),
                AcceptanceCriterion.mandatory.is_(True),
                AcceptanceCriterion.change_kind.is_(None),
            )
        )
    ).scalars()
    rows: list[VerificationObligation] = []
    for ac in acs:
        spec = await session.get(FeatureSpec, ac.feature_spec_id)
        path = f"{spec.lineage_key if spec else 'spec'}/{ac.lineage_key}"
        if not any(ref in path or ref in ac.lineage_key for ref in changed_refs):
            continue
        rows.append(
            VerificationObligation(
                delivery_cycle_id=ic.delivery_cycle_id,
                integration_candidate_id=ic.id,
                gate_type=GateType.SENTINEL.value,
                subject_type="AC",
                subject_id=ac.id,
                subject_key=ac.lineage_key,
                required=True,
                allowed_evidence_types=allowed_evidence_types(ac.evidence_requirement),
                reason=ObligationReason.AC_REVALIDATION,
                source_refs=[{"type": "ACCEPTANCE_CRITERION", "id": str(ac.id), "path": path}],
                status=ObligationStatus.OPEN,
            )
        )
    return rows


async def _baseline_source(
    session: AsyncSession,
    ic: IntegrationCandidate,
    ctx: CommandContext,
) -> list[VerificationObligation]:
    impact_rows = await _impact_baseline_and_test_source(session, ic, ctx)
    if impact_rows:
        return impact_rows
    from core.domain.delivery_cycles.models import DeliveryCycle
    from core.domain.projects.models import Project
    from core.intelligence.baselines.enums import BaselineStatus
    from core.intelligence.baselines.models import BaselineSet, BaselineSetItem, BehavioralBaseline

    cycle = await session.get(DeliveryCycle, ic.delivery_cycle_id)
    if cycle is None:
        return []
    project = await session.get(Project, cycle.project_id)
    if project is None or project.active_baseline_set_id is None:
        return []
    bset = await session.get(BaselineSet, project.active_baseline_set_id)
    if bset is None:
        return []
    items = (
        (
            await session.execute(
                select(BaselineSetItem).where(BaselineSetItem.baseline_set_id == bset.id)
            )
        )
        .scalars()
        .all()
    )
    superseded_ids, approval_key = await _superseded_baseline_note(session, cycle.id)
    rows: list[VerificationObligation] = []
    for item in items:
        bl = await session.get(BehavioralBaseline, item.baseline_id)
        if bl is None or bl.status != BaselineStatus.ACTIVE:
            continue
        if bl.id in superseded_ids:
            rows.append(
                VerificationObligation(
                    delivery_cycle_id=ic.delivery_cycle_id,
                    integration_candidate_id=ic.id,
                    gate_type=GateType.BASELINE.value,
                    subject_type="BASELINE",
                    subject_id=bl.id,
                    subject_key=bl.lineage_key,
                    required=False,
                    allowed_evidence_types=["UNIT_TEST", "API_TEST", "INTEGRATION_TEST"],
                    reason=ObligationReason.BASELINE_REQUIRED,
                    source_refs=[
                        {
                            "type": "BASELINE",
                            "id": str(bl.id),
                            "baseline_set_key": bset.key,
                            "superseded_by_approved_expected_behavior": approval_key,
                        }
                    ],
                    status=ObligationStatus.OPEN,
                )
            )
            continue
        rows.append(
            VerificationObligation(
                delivery_cycle_id=ic.delivery_cycle_id,
                integration_candidate_id=ic.id,
                gate_type=GateType.BASELINE.value,
                subject_type="BASELINE",
                subject_id=bl.id,
                subject_key=bl.lineage_key,
                required=not bl.provisional,
                allowed_evidence_types=["UNIT_TEST", "API_TEST", "INTEGRATION_TEST"],
                reason=ObligationReason.BASELINE_REQUIRED,
                source_refs=[
                    {
                        "type": "BASELINE",
                        "id": str(bl.id),
                        "baseline_set_key": bset.key,
                    }
                ],
                status=ObligationStatus.OPEN,
            )
        )
    return rows


if not _SOURCES:
    register_obligation_source(_ac_source)
    register_obligation_source(_ac_revalidation_source)
    register_obligation_source(_baseline_source)

import core.assurance.bugfix_obligations  # noqa: F401, E402


class ObligationService:
    def __init__(self) -> None:
        pass

    async def derive(
        self,
        session: AsyncSession,
        ic_id: uuid.UUID,
        ctx: CommandContext,
    ) -> list[VerificationObligation]:
        ic = await session.get(IntegrationCandidate, ic_id)
        if ic is None or ic.integrated_sha is None:
            raise ValueError("IC not ready")
        rows: list[VerificationObligation] = []
        for source in _SOURCES:
            rows.extend(await source(session, ic, ctx))
        for row in rows:
            session.add(row)
        await session.flush()
        for row in rows:
            await append_domain_event(
                session,
                aggregate_type="verification_obligation",
                aggregate_id=row.id,
                event_type="obligation.derived",
                payload={"subject_key": row.subject_key, "reason": row.reason.value},
                actor_id=ctx.actor.id,
                correlation_id=ctx.correlation_id,
                delivery_cycle_id=ic.delivery_cycle_id,
            )
        return rows
