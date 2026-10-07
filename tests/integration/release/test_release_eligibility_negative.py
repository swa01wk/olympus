"""Phase 10 — release cannot become eligible when prerequisites fail."""

from __future__ import annotations

import pytest
from core.assurance.enums import GateStatus, GateType
from core.integration.enums import FindingSeverity, FindingSource
from core.release.enums import ReleaseStatus
from core.release.models import ReleaseEligibilityEvaluation
from core.release.service import ReleaseService
from tests.fixtures.assurance_harness import (
    finalize_all_pending_gates,
    gate_by_type,
    human_finalize_ctx,
)
from tests.fixtures.release_harness import (
    advance_cycle_through_assurance,
    build_ic_through_integration_phase,
    seed_approved_scope_for_feature_spec,
)

pytestmark = [pytest.mark.integration, pytest.mark.git]


@pytest.mark.asyncio
async def test_not_eligible_when_scope_missing(
    db_session,
    system_ctx,
    operator_ctx,
) -> None:
    ic, lineage, fixture = await build_ic_through_integration_phase(
        db_session, system_ctx, project_key="rel-noscope", passing=True
    )
    await advance_cycle_through_assurance(db_session, fixture.cycle.id, system_ctx)
    fin_ctx = await human_finalize_ctx(db_session)
    await finalize_all_pending_gates(db_session, ic.id, fin_ctx)
    release = await ReleaseService().create_release(db_session, fixture.cycle.id, system_ctx)
    await db_session.refresh(release)
    assert release.status == ReleaseStatus.NOT_ELIGIBLE
    ev = await db_session.get(ReleaseEligibilityEvaluation, release.latest_eligibility_id)
    assert ev is not None and ev.eligible is False
    approvals = next(c for c in ev.conditions if c["name"] == "required_approvals_exist")
    assert approvals["ok"] is False


@pytest.mark.asyncio
async def test_not_eligible_when_gate_pending(
    db_session,
    system_ctx,
    operator_ctx,
) -> None:
    ic, lineage, fixture = await build_ic_through_integration_phase(
        db_session, system_ctx, project_key="rel-gate", passing=True
    )
    await seed_approved_scope_for_feature_spec(
        db_session, fixture.cycle, lineage.feature_spec_id, operator_ctx
    )
    await advance_cycle_through_assurance(db_session, fixture.cycle.id, system_ctx)
    release = await ReleaseService().create_release(db_session, fixture.cycle.id, system_ctx)
    await db_session.refresh(release)
    assert release.status == ReleaseStatus.NOT_ELIGIBLE
    ev = await db_session.get(ReleaseEligibilityEvaluation, release.latest_eligibility_id)
    assert ev is not None
    gates_cond = next(c for c in ev.conditions if c["name"] == "required_gates_pass")
    assert gates_cond["ok"] is False


@pytest.mark.asyncio
async def test_not_eligible_when_blocking_finding_open(
    db_session,
    system_ctx,
    operator_ctx,
) -> None:
    ic, lineage, fixture = await build_ic_through_integration_phase(
        db_session, system_ctx, project_key="rel-find", passing=True
    )
    await seed_approved_scope_for_feature_spec(
        db_session, fixture.cycle, lineage.feature_spec_id, operator_ctx
    )
    await advance_cycle_through_assurance(db_session, fixture.cycle.id, system_ctx)
    fin_ctx = await human_finalize_ctx(db_session)
    await finalize_all_pending_gates(db_session, ic.id, fin_ctx)

    from core.assurance.findings import FindingService

    await FindingService().create(
        db_session,
        project_id=fixture.project.id,
        delivery_cycle_id=fixture.cycle.id,
        integration_candidate_id=ic.id,
        title="blocking",
        detail={"test": True},
        severity=FindingSeverity.BLOCKER,
        source=FindingSource.WARDEN,
        category="TEST",
        ctx=system_ctx,
    )
    await ReleaseService().maybe_advance_cycle_to_release(db_session, fixture.cycle.id, system_ctx)
    release = await ReleaseService().create_release(db_session, fixture.cycle.id, system_ctx)
    await db_session.refresh(release)
    assert release.status == ReleaseStatus.NOT_ELIGIBLE
    ev = await db_session.get(ReleaseEligibilityEvaluation, release.latest_eligibility_id)
    assert ev is not None
    blocking = next(c for c in ev.conditions if c["name"] == "blocking_findings")
    assert blocking["ok"] is False


@pytest.mark.asyncio
async def test_not_eligible_when_mandatory_evidence_missing(
    db_session,
    system_ctx,
    operator_ctx,
) -> None:
    ic, lineage, fixture = await build_ic_through_integration_phase(
        db_session, system_ctx, project_key="rel-ev", passing=False
    )
    await seed_approved_scope_for_feature_spec(
        db_session, fixture.cycle, lineage.feature_spec_id, operator_ctx
    )
    await advance_cycle_through_assurance(db_session, fixture.cycle.id, system_ctx)
    fin_ctx = await human_finalize_ctx(db_session)
    gates = await finalize_all_pending_gates(db_session, ic.id, fin_ctx)
    sentinel = gate_by_type(gates, GateType.SENTINEL)
    assert sentinel.status == GateStatus.FAIL
    release = await ReleaseService().create_release(db_session, fixture.cycle.id, system_ctx)
    await db_session.refresh(release)
    assert release.status == ReleaseStatus.NOT_ELIGIBLE
    ev = await db_session.get(ReleaseEligibilityEvaluation, release.latest_eligibility_id)
    assert ev is not None and ev.eligible is False
