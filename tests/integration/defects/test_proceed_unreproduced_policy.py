"""proceed_unreproduced respects bugfix.allow_unreproduced policy (Phase 15 §12)."""

from __future__ import annotations

from pathlib import Path

import pytest
from core.commands.context import CommandContext
from core.domain.exceptions import DomainError
from core.product_model.defects.service import DefectService
from tests.fixtures.brownfield_phase12_harness import ensure_human_approver
from tests.journey.seed import seed_trusted_project

DEFECT_REPO = (
    Path(__file__).resolve().parents[2] / "fixtures" / "repos" / "supportdesk_defect_closed_update"
)
TRUSTED_SEED_DEFECT = (
    Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "trusted_seed_defect.yaml"
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_proceed_unreproduced_rejected_when_policy_forbids(
    db_session, system_ctx: CommandContext
) -> None:
    trusted = await seed_trusted_project(db_session, DEFECT_REPO, TRUSTED_SEED_DEFECT, system_ctx)
    defect = await DefectService().intake(
        db_session,
        project_id=trusted.project_id,
        title="not repro",
        description="x",
        source_type="test",
        external_ref="unrepro-pol-1",
        inbound_event_id=None,
        ctx=system_ctx,
    )
    defect.status = "NOT_REPRODUCIBLE"
    await db_session.flush()
    _human, human_ctx = await ensure_human_approver(db_session)
    with pytest.raises(DomainError) as exc_info:
        await DefectService().proceed_unreproduced(
            db_session,
            defect.id,
            human_ctx,
            reason="attempt without policy",
        )
    assert exc_info.value.code == "POLICY_FORBIDS"
