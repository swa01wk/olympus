"""Defect intake idempotency (Phase 15 persistence tests)."""

from __future__ import annotations

from pathlib import Path

import pytest
from core.commands.context import CommandContext
from core.product_model.defects.models import Defect
from core.product_model.defects.service import DefectService
from sqlalchemy import func, select
from tests.journey.seed import seed_trusted_project

DEFECT_REPO = (
    Path(__file__).resolve().parents[2] / "fixtures" / "repos" / "supportdesk_defect_closed_update"
)
TRUSTED_SEED_DEFECT = (
    Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "trusted_seed_defect.yaml"
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_defect_intake_idempotent_by_external_ref(
    db_session, system_ctx: CommandContext
) -> None:
    trusted = await seed_trusted_project(db_session, DEFECT_REPO, TRUSTED_SEED_DEFECT, system_ctx)
    svc = DefectService()
    first = await svc.intake(
        db_session,
        project_id=trusted.project_id,
        title="dup",
        description="same defect",
        source_type="test-intake",
        external_ref="EXT-1",
        inbound_event_id=None,
        ctx=system_ctx,
    )
    second = await svc.intake(
        db_session,
        project_id=trusted.project_id,
        title="dup",
        description="same defect",
        source_type="test-intake",
        external_ref="EXT-1",
        inbound_event_id=None,
        ctx=system_ctx,
    )
    assert first.id == second.id
    count = await db_session.scalar(
        select(func.count()).select_from(Defect).where(Defect.external_ref == "EXT-1")
    )
    assert count == 1
    assert first.delivery_cycle_id is not None
