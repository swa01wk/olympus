from __future__ import annotations

import pytest
from core.assurance.obligations import ObligationService
from core.integration.enums import ICStatus
from core.integration.models import IntegrationCandidate
from core.intelligence.impact.engine import ImpactEngine
from core.intelligence.impact.models import ImpactItem
from core.product_model.specifications.delta import SpecDeltaService
from sqlalchemy import select
from tests.fixtures.impact_harness import seed_supportdesk_ticket_priority_impact

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_obligations_only_from_structural_selection(db_session, system_ctx) -> None:
    fx = await seed_supportdesk_ticket_priority_impact(db_session, system_ctx)
    delta = await SpecDeltaService().compute(
        db_session,
        from_spec_id=fx.spec_v1_id,
        to_spec_id=fx.spec_v2_id,
        delivery_cycle_id=fx.cycle_id,
        ctx=system_ctx,
    )
    await ImpactEngine().assess(
        db_session,
        fx.cycle_id,
        spec_delta_id=delta.id,
        index_version_id=fx.index_version.id,
        ctx=system_ctx,
    )
    ic = IntegrationCandidate(
        key="IC-IMPACT-1",
        delivery_cycle_id=fx.cycle_id,
        repository_id=fx.repository_id,
        status=ICStatus.READY,
        integrated_sha=fx.commit_sha,
        base_sha=fx.commit_sha,
        integration_branch="refs/heads/olympus/integration/impact-test",
    )
    db_session.add(ic)
    await db_session.flush()

    rows = await ObligationService().derive(db_session, ic.id, system_ctx)
    assert rows
    for row in rows:
        reason = row.reason.value if hasattr(row.reason, "value") else str(row.reason)
        assert reason in {"IMPACT_ASSESSMENT", "BASELINE_REQUIRED", "AC_MANDATORY"}
        assert row.source_refs

    items = (
        await db_session.execute(
            select(ImpactItem).where(
                ImpactItem.impact_kind.in_(("CANDIDATE", "SEMANTIC_CANDIDATE"))
            )
        )
    ).scalars()
    for item in items:
        assert item.selected_for_verification is False
