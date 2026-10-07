from __future__ import annotations

import pytest
from core.assurance.models import Finding
from core.domain.delivery_cycles.models import DeliveryCycle
from core.integration.enums import FindingStatus
from core.intelligence.impact.staleness import StalenessService
from sqlalchemy import select
from tests.fixtures.impact_harness import seed_supportdesk_ticket_priority_impact

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_cycle_base_diverged_finding_cleared_by_rebase(db_session, system_ctx) -> None:
    fx = await seed_supportdesk_ticket_priority_impact(db_session, system_ctx)
    cycle = await db_session.get(DeliveryCycle, fx.cycle_id)
    assert cycle is not None
    cycle.base_sha = fx.commit_sha
    await db_session.flush()

    diverged_sha = "a" * 40
    await StalenessService().on_canonical_revision_changed(
        db_session,
        fx.repository_id,
        fx.commit_sha,
        diverged_sha,
        "CANONICAL_REVISION_CHANGED",
        ctx=system_ctx,
    )
    finding = (
        await db_session.execute(
            select(Finding).where(
                Finding.delivery_cycle_id == fx.cycle_id,
                Finding.category == "CYCLE_BASE_DIVERGED",
                Finding.status == FindingStatus.OPEN,
            )
        )
    ).scalar_one_or_none()
    assert finding is not None

    finding.status = FindingStatus.RESOLVED
    cycle.base_sha = diverged_sha
    await db_session.flush()
    await db_session.refresh(cycle)
    assert cycle.base_sha == diverged_sha
