"""Phase 09 §12 — supportdesk_r1 IC with three mandatory ACs and real sentinel.execute."""

from __future__ import annotations

import pytest
from core.assurance.enums import EvidenceProducer, EvidenceResult, GateStatus, GateType
from core.assurance.models import Evidence
from sqlalchemy import select
from tests.fixtures.assurance_harness import (
    finalize_all_pending_gates,
    gate_by_type,
    human_finalize_ctx,
)
from tests.fixtures.assurance_supportdesk_harness import supportdesk_ic_with_real_sentinel

pytestmark = [pytest.mark.integration, pytest.mark.git]


@pytest.mark.asyncio
async def test_supportdesk_r1_three_ac_sentinel_gate_pass(db_session, system_ctx) -> None:
    ic, fixture = await supportdesk_ic_with_real_sentinel(
        db_session, system_ctx, project_key_suffix="sd-pass", passing=True
    )
    rows = (
        (
            await db_session.execute(
                select(Evidence).where(
                    Evidence.integration_candidate_id == ic.id,
                    Evidence.producer == EvidenceProducer.SENTINEL,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) >= 3, "expected sentinel evidence for mapped AC obligations"
    assert all(r.result == EvidenceResult.PASS for r in rows)
    assert fixture.ac_lineage_keys == ("AC-1", "AC-2", "AC-3")

    fin_ctx = await human_finalize_ctx(db_session)
    gates = await finalize_all_pending_gates(db_session, ic.id, fin_ctx)
    sentinel = gate_by_type(gates, GateType.SENTINEL)
    assert sentinel.status == GateStatus.PASS, sentinel.reasons


@pytest.mark.asyncio
async def test_supportdesk_r1_break_test_sentinel_gate_fail(db_session, system_ctx) -> None:
    ic, fixture = await supportdesk_ic_with_real_sentinel(
        db_session, system_ctx, project_key_suffix="sd-fail", passing=False
    )
    fin_ctx = await human_finalize_ctx(db_session)
    gates = await finalize_all_pending_gates(db_session, ic.id, fin_ctx)
    sentinel = gate_by_type(gates, GateType.SENTINEL)
    assert sentinel.status == GateStatus.FAIL
    assert any(
        r.startswith("OBLIGATION_UNSATISFIED:") and key in r
        for r in (sentinel.reasons or [])
        for key in ("AC-2", "AC-3")
    )
