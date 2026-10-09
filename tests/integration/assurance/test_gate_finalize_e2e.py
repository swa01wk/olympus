"""Phase 09 §12 integration — gate finalizer on real IC evidence (supportdesk-style harness)."""

from __future__ import annotations

import uuid

import pytest
from core.assurance.enums import (
    EvidenceProducer,
    EvidenceResult,
    EvidenceType,
    GateStatus,
    GateType,
)
from core.assurance.evidence import EvidenceService
from core.assurance.gates import GateFinalizerService
from core.assurance.models import Gate
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.repositories.models import Repository
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from tests.fixtures.assurance_harness import (
    finalize_all_pending_gates,
    gate_by_type,
    human_finalize_ctx,
    ready_ic_with_sentinel_evidence,
)

pytestmark = [pytest.mark.integration, pytest.mark.git]


@pytest.mark.asyncio
async def test_supportdesk_style_sentinel_gate_pass_when_checks_pass(
    db_session,
    system_ctx,
) -> None:
    ic, _, _ = await ready_ic_with_sentinel_evidence(
        db_session, system_ctx, project_key="p9-pass", passing=True
    )
    fin_ctx = await human_finalize_ctx(db_session)
    gates = await finalize_all_pending_gates(db_session, ic.id, fin_ctx)
    sentinel = gate_by_type(gates, GateType.SENTINEL)
    assert sentinel.status == GateStatus.PASS, sentinel.reasons
    integration = gate_by_type(gates, GateType.INTEGRATION)
    assert integration.status == GateStatus.PASS
    warden = gate_by_type(gates, GateType.WARDEN)
    assert warden.status == GateStatus.PASS


@pytest.mark.asyncio
async def test_sentinel_gate_fail_when_mandatory_check_fails(
    db_session,
    system_ctx,
    force_sentinel_fail,
) -> None:
    ic, lineage, _ = await ready_ic_with_sentinel_evidence(
        db_session, system_ctx, project_key="p9-fail", passing=True
    )
    fin_ctx = await human_finalize_ctx(db_session)
    gates = await finalize_all_pending_gates(db_session, ic.id, fin_ctx)
    sentinel = gate_by_type(gates, GateType.SENTINEL)
    assert sentinel.status == GateStatus.FAIL
    assert any(
        r.startswith("OBLIGATION_UNSATISFIED:") and lineage.ac_lineage_key in r
        for r in (sentinel.reasons or [])
    )


@pytest.mark.asyncio
async def test_finalize_ignores_wrong_sha_evidence(
    db_session,
    system_ctx,
) -> None:
    ic, _, fixture = await ready_ic_with_sentinel_evidence(
        db_session, system_ctx, project_key="p9-sha", passing=True
    )
    cycle = await db_session.get(DeliveryCycle, fixture.cycle.id)
    assert cycle is not None
    await EvidenceService().record(
        db_session,
        project_id=cycle.project_id,
        delivery_cycle_id=cycle.id,
        integration_candidate_id=ic.id,
        commit_sha="0" * 40,
        evidence_type=EvidenceType.UNIT_TEST,
        result=EvidenceResult.PASS,
        subject_type="AC",
        subject_id=uuid.uuid4(),
        check_ref="wrong-sha",
        producer=EvidenceProducer.SENTINEL,
        ctx=system_ctx,
    )
    sentinel = (
        await db_session.execute(
            select(Gate).where(
                Gate.integration_candidate_id == ic.id,
                Gate.gate_type == GateType.SENTINEL,
            )
        )
    ).scalar_one()
    repo = await db_session.get(Repository, fixture.repository.id)
    decision = await GateFinalizerService()._compute_decision(db_session, sentinel, ic, repo)
    assert decision.status == GateStatus.FAIL
    assert any(str(r).startswith("EVIDENCE_SHA_MISMATCH") for r in decision.reasons)


@pytest.mark.asyncio
async def test_finalize_fail_closed_on_canonical_revision_mismatch(
    db_session,
    system_ctx,
) -> None:
    ic, _, fixture = await ready_ic_with_sentinel_evidence(
        db_session, system_ctx, project_key="p9-canonical", passing=True
    )
    repo = await db_session.get(Repository, fixture.repository.id)
    assert repo is not None and repo.canonical_commit == ic.integrated_sha
    sentinel = (
        await db_session.execute(
            select(Gate).where(
                Gate.integration_candidate_id == ic.id,
                Gate.gate_type == GateType.SENTINEL,
            )
        )
    ).scalar_one()
    repo = await db_session.get(Repository, fixture.repository.id)
    assert repo is not None
    with db_session.no_autoflush:
        repo.canonical_commit = ic.base_sha
        decision = await GateFinalizerService()._compute_decision(db_session, sentinel, ic, repo)
    assert decision.status == GateStatus.FAIL
    assert "CANONICAL_REVISION_MISMATCH" in decision.reasons


@pytest.mark.asyncio
async def test_finalized_gate_status_immutable(db_session, system_ctx) -> None:
    ic, _, _ = await ready_ic_with_sentinel_evidence(
        db_session, system_ctx, project_key="p9-immut-a", passing=True
    )
    fin_ctx = await human_finalize_ctx(db_session)
    gates = await finalize_all_pending_gates(db_session, ic.id, fin_ctx)
    sentinel = gate_by_type(gates, GateType.SENTINEL)
    sentinel.status = GateStatus.PENDING
    with pytest.raises(DBAPIError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_gate_finalized_by_must_be_system(db_session, system_ctx) -> None:
    ic, _, _ = await ready_ic_with_sentinel_evidence(
        db_session, system_ctx, project_key="p9-immut-b", passing=True
    )
    warden = (
        await db_session.execute(
            select(Gate).where(
                Gate.integration_candidate_id == ic.id,
                Gate.gate_type == GateType.WARDEN,
            )
        )
    ).scalar_one()
    warden.status = GateStatus.PASS
    warden.finalized_by = "AGENT:warden"
    with pytest.raises(DBAPIError):
        await db_session.flush()
