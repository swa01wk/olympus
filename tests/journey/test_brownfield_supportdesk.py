"""Journey 2 — brownfield onboarding to READY_FOR_CHANGE (live Scout + workflow path)."""

from __future__ import annotations

import os
import uuid
from unittest.mock import patch

import pytest
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ProjectReadiness
from core.domain.projects.models import Project
from core.runtime.model_router import build_providers
from core.runtime.providers.fake_provider import FakeProvider
from core.state.transition_service import TransitionService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from tests.fixtures.brownfield_harness import brownfield_cycle_at_code_index
from tests.fixtures.brownfield_phase12_harness import (
    advance_to_ready_for_change,
    ensure_human_approver,
    live_drain_spec_recovery,
    run_baseline_stage_workers,
    transition_validated_recovery_to_baseline,
)
from tests.fixtures.planning_workflow_harness import ensure_system_actor
from tests.journey.helpers import assert_live_llm_proof
from tests.live_credentials import any_live_provider_configured

pytestmark = [
    pytest.mark.journey,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.environ.get("LLM_LIVE_TESTS") != "1",
        reason="Set LLM_LIVE_TESTS=1 for live brownfield journey",
    ),
]


@pytest.mark.asyncio
async def test_brownfield_supportdesk_ready_for_change(async_engine: AsyncEngine) -> None:
    if not any_live_provider_configured():
        pytest.skip("No live provider API key configured")

    os.environ.setdefault(
        "MODEL_REPOSITORY_REASONING",
        os.environ.get("MODEL_DEFAULT", ""),
    )
    from core.config.settings import clear_settings_cache
    from core.runtime.model_policy import clear_models_config_cache

    clear_settings_cache()
    clear_models_config_cache()

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    cycle_id: uuid.UUID

    async with factory() as session, session.begin():
        actor = await ensure_system_actor(session)
        setup_ctx = CommandContext(actor=actor, correlation_id="bf-journey-live-setup")
        cycle, _sha, _repo = await brownfield_cycle_at_code_index(session, setup_ctx)
        cycle_id = cycle.id
        await TransitionService().transition(
            session,
            "delivery_cycle",
            cycle_id,
            "CODE_INDEX",
            "start_spec_recovery",
            setup_ctx,
        )

    with patch("core.runtime.model_router.build_providers", side_effect=build_providers):
        await live_drain_spec_recovery(factory, cycle_id)

    async with factory() as session, session.begin():
        actor = await ensure_system_actor(session)
        system_ctx = CommandContext(actor=actor, correlation_id="bf-journey-live")
        cycle = await transition_validated_recovery_to_baseline(session, cycle_id, system_ctx)
        characterize_fake = FakeProvider()
        await run_baseline_stage_workers(session, system_ctx, cycle.id, fake=characterize_fake)
        _human, human_ctx = await ensure_human_approver(session)
        final = await advance_to_ready_for_change(session, cycle.id, system_ctx, human_ctx)
        assert final.state == "READY"

    async with factory() as session:
        cycle = await session.get(DeliveryCycle, cycle_id)
        assert cycle is not None
        project = await session.get(Project, cycle.project_id)
        assert project is not None
        assert project.readiness_state == ProjectReadiness.READY_FOR_CHANGE
        assert project.active_baseline_set_id is not None
        from core.intelligence.baselines.enums import BaselineStatus
        from core.intelligence.baselines.models import BehavioralBaseline

        active = (
            await session.execute(
                select(BehavioralBaseline).where(
                    BehavioralBaseline.project_id == cycle.project_id,
                    BehavioralBaseline.status == BaselineStatus.ACTIVE,
                )
            )
        ).scalars()
        assert len(list(active)) >= 1
        await assert_live_llm_proof(
            session,
            cycle_id,
            ("repository_reasoning",),
        )
