"""TOCTOU — eligibility re-checked at stratos.release execution."""

from __future__ import annotations

import pytest
from core.assurance.findings import FindingService
from core.integration.enums import FindingSeverity, FindingSource
from core.release.enums import ReleaseStatus
from tests.fixtures.release_harness import (
    ready_eligible_release,
)

pytestmark = [pytest.mark.integration, pytest.mark.git]


@pytest.mark.asyncio
async def test_execution_fails_when_eligibility_lost_after_approval(
    db_session,
    system_ctx,
    operator_ctx,
) -> None:
    ic, fixture, release = await ready_eligible_release(
        db_session, system_ctx, operator_ctx, project_key="rel-toctou"
    )
    from core.release.service import ReleaseService

    await ReleaseService().approve_release(db_session, release.id, operator_ctx)
    await db_session.refresh(release)
    assert release.status == ReleaseStatus.APPROVED

    await ReleaseService().execute_release(db_session, release.id, system_ctx)

    await FindingService().create(
        db_session,
        project_id=fixture.project.id,
        delivery_cycle_id=fixture.cycle.id,
        integration_candidate_id=ic.id,
        title="post-approval block",
        detail={"reason": "toctou"},
        severity=FindingSeverity.BLOCKER,
        source=FindingSource.SYSTEM,
        category="TOCTOU_TEST",
        ctx=system_ctx,
    )
    from tests.fixtures.assurance_harness import run_worker_rounds

    await run_worker_rounds(db_session, system_ctx, max_rounds=40)
    await db_session.refresh(release)
    assert release.status == ReleaseStatus.FAILED
