from __future__ import annotations

import pytest
from core.commands.context import CommandContext
from core.domain.enums import ProjectReadiness, SpecStatus
from core.domain.projects.models import Project
from core.intelligence.baselines.enums import BaselineStatus
from core.intelligence.baselines.models import BehavioralBaseline
from core.product_model.models import FeatureSpec
from sqlalchemy import select
from tests.fixtures.code_index_harness import SUPPORTDESK_R1
from tests.journey.seed import TRUSTED_SEED, seed_trusted_project


@pytest.mark.integration
@pytest.mark.asyncio
async def test_trusted_seed_ready_for_change(db_session, system_ctx: CommandContext) -> None:
    trusted = await seed_trusted_project(db_session, SUPPORTDESK_R1, TRUSTED_SEED, system_ctx)
    project = await db_session.get(Project, trusted.project_id)
    assert project is not None
    assert project.readiness_state == ProjectReadiness.READY_FOR_CHANGE
    assert project.active_baseline_set_id == trusted.baseline_set_id

    spec = await db_session.get(FeatureSpec, trusted.feature_spec_id)
    assert spec is not None and spec.status == SpecStatus.APPROVED

    baselines = list(
        (
            await db_session.execute(
                select(BehavioralBaseline).where(
                    BehavioralBaseline.project_id == trusted.project_id,
                    BehavioralBaseline.status == BaselineStatus.ACTIVE,
                )
            )
        ).scalars()
    )
    assert len(baselines) >= 2
