from __future__ import annotations

import pytest
from core.domain.approvals.service import ApprovalService
from core.domain.enums import ApprovalStatus, ApprovalType
from core.intelligence.impact.enums import ImpactAssessmentStatus, SpecDeltaStatus
from core.intelligence.impact.models import ImpactAssessment, SpecDelta
from core.product_model.specifications.delta import SpecDeltaService
from tests.fixtures.impact_harness import seed_supportdesk_ticket_priority_impact

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_spec_delta_approved_immutable_hash(
    db_session, system_ctx, operator_ctx, sample_project
) -> None:
    fx = await seed_supportdesk_ticket_priority_impact(db_session, system_ctx)
    delta = await SpecDeltaService().compute(
        db_session,
        from_spec_id=fx.spec_v1_id,
        to_spec_id=fx.spec_v2_id,
        delivery_cycle_id=fx.cycle_id,
        ctx=system_ctx,
    )
    original_hash = delta.content_hash
    approval_id = (
        await SpecDeltaService().request_approval(db_session, delta.id, system_ctx)
    ).approval_id
    assert approval_id
    await ApprovalService().decide(
        db_session, approval_id, ApprovalStatus.APPROVED, None, operator_ctx
    )
    await SpecDeltaService().mark_approved(db_session, delta.id, approval_id, operator_ctx)
    row = await db_session.get(SpecDelta, delta.id)
    assert row is not None
    assert row.status == SpecDeltaStatus.APPROVED.value
    assert row.content_hash == original_hash
    satisfied = await ApprovalService().is_satisfied(
        db_session,
        ApprovalType.SPEC_DELTA,
        "SPEC_DELTA",
        delta.id,
        original_hash,
    )
    assert satisfied
    assert not await ApprovalService().is_satisfied(
        db_session,
        ApprovalType.SPEC_DELTA,
        "SPEC_DELTA",
        delta.id,
        "wrong-hash",
    )


@pytest.mark.asyncio
async def test_impact_assessment_complete_status_pinned(db_session, system_ctx) -> None:
    fx = await seed_supportdesk_ticket_priority_impact(db_session, system_ctx)
    ia = ImpactAssessment(
        key="IA-1",
        delivery_cycle_id=fx.cycle_id,
        index_version_id=fx.index_version.id,
        commit_sha=fx.commit_sha,
        seed_kind="MANUAL",
        seed_refs=[],
        status=ImpactAssessmentStatus.COMPLETE.value,
        architecture_delta_suggested=False,
        summary={},
        content_hash="abc",
    )
    db_session.add(ia)
    await db_session.flush()
    ia.status = ImpactAssessmentStatus.STALE.value
    await db_session.flush()
    refreshed = await db_session.get(ImpactAssessment, ia.id)
    assert refreshed is not None
    assert refreshed.status == ImpactAssessmentStatus.STALE.value
