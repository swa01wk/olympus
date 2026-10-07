from __future__ import annotations

import pytest
from core.assurance.models import Finding
from core.integration.enums import SpecCodeLinkOrigin, SpecCodeLinkRelation, SpecCodeLinkStatus
from core.traceability.models import SpecCodeLink
from core.traceability.spec_code_links.refresh import SpecCodeLinkRefreshService
from sqlalchemy import select
from tests.fixtures.impact_harness import seed_supportdesk_ticket_priority_impact

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_missing_principal_marks_link_stale(db_session, system_ctx) -> None:
    fx = await seed_supportdesk_ticket_priority_impact(db_session, system_ctx)
    missing_key = "METHOD:app/services/ticket_service.py:TicketService.create"
    link = SpecCodeLink(
        project_id=fx.project_id,
        repository_id=fx.repository_id,
        spec_type="FEATURE_SPEC",
        spec_id=fx.spec_v2_id,
        spec_lineage_key="SPEC-FEAT-TICKETS",
        code_stable_key=missing_key,
        relation=SpecCodeLinkRelation.IMPLEMENTS,
        origin=SpecCodeLinkOrigin.HUMAN_CONFIRMED,
        confidence=1.0,
        established_index_version_id=fx.index_version.id,
        last_confirmed_index_version_id=fx.index_version.id,
        status=SpecCodeLinkStatus.ACTIVE,
    )
    db_session.add(link)
    await db_session.flush()

    report = await SpecCodeLinkRefreshService().refresh(
        db_session,
        repository_id=fx.repository_id,
        canonical_index_version_id=fx.index_version.id,
        delivery_cycle_id=fx.cycle_id,
        project_id=fx.project_id,
        ctx=system_ctx,
    )
    assert missing_key in report.stale_links
    await db_session.refresh(link)
    assert link.status == SpecCodeLinkStatus.STALE
    findings = (
        await db_session.execute(select(Finding).where(Finding.category == "LINEAGE_LINK_STALE"))
    ).scalars()
    assert any(missing_key in f.title for f in findings)
    assert report.artifact_id is not None
