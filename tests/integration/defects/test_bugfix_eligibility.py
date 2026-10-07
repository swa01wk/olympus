"""Bug-fix release eligibility conditions (Phase 15 §12)."""

from __future__ import annotations

from pathlib import Path

import pytest
from core.domain.delivery_cycles.models import DeliveryCycle
from core.integration.enums import ICStatus
from core.integration.models import IntegrationCandidate
from core.product_model.defects.service import DefectService
from core.release.bugfix_eligibility import _cond_defect_reproduced_before_repair
from tests.journey.bug_fix_helpers import bootstrap_bug_fix_to_root_cause
from tests.journey.seed import seed_trusted_project

DEFECT_REPO = (
    Path(__file__).resolve().parents[2] / "fixtures" / "repos" / "supportdesk_defect_closed_update"
)
TRUSTED_SEED_DEFECT = (
    Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "trusted_seed_defect.yaml"
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_defect_reproduced_before_repair_passes_with_valid_pre_repair(
    db_session, system_ctx
) -> None:
    trusted = await seed_trusted_project(db_session, DEFECT_REPO, TRUSTED_SEED_DEFECT, system_ctx)
    d = await DefectService().intake(
        db_session,
        project_id=trusted.project_id,
        title="eligibility ok",
        description="PATCH on CLOSED ticket returns 500 not 409",
        source_type="test",
        external_ref="elig-ok-1",
        inbound_event_id=None,
        ctx=system_ctx,
    )
    assert d.delivery_cycle_id is not None
    await bootstrap_bug_fix_to_root_cause(db_session, d.delivery_cycle_id, system_ctx)
    cycle = await db_session.get(DeliveryCycle, d.delivery_cycle_id)
    assert cycle is not None
    ic = IntegrationCandidate(
        key="IC-ELIG2",
        delivery_cycle_id=cycle.id,
        repository_id=trusted.repository_id,
        status=ICStatus.READY,
        integrated_sha="d" * 40,
        base_sha=cycle.base_sha or ("b" * 40),
        integration_branch="refs/heads/olympus/integration/elig2",
    )
    db_session.add(ic)
    await db_session.flush()
    result = await _cond_defect_reproduced_before_repair(db_session, cycle, ic, None, {})
    assert result.ok


@pytest.mark.integration
@pytest.mark.asyncio
async def test_defect_reproduced_before_repair_fails_without_pre_repair(
    db_session, system_ctx
) -> None:
    trusted = await seed_trusted_project(db_session, DEFECT_REPO, TRUSTED_SEED_DEFECT, system_ctx)
    d = await DefectService().intake(
        db_session,
        project_id=trusted.project_id,
        title="no repro",
        description="x",
        source_type="test",
        external_ref="elig-miss-1",
        inbound_event_id=None,
        ctx=system_ctx,
    )
    assert d.delivery_cycle_id is not None
    cycle = await db_session.get(DeliveryCycle, d.delivery_cycle_id)
    assert cycle is not None
    ic = IntegrationCandidate(
        key="IC-ELIG3",
        delivery_cycle_id=cycle.id,
        repository_id=trusted.repository_id,
        status=ICStatus.READY,
        integrated_sha="e" * 40,
        base_sha=d.affected_sha,
        integration_branch="refs/heads/olympus/integration/elig3",
    )
    db_session.add(ic)
    await db_session.flush()
    result = await _cond_defect_reproduced_before_repair(db_session, cycle, ic, None, {})
    assert not result.ok
    assert "PRE_REPAIR_MISSING" in result.reasons
