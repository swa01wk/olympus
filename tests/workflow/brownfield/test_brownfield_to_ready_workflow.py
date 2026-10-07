"""Brownfield onboarding through READY_FOR_CHANGE (FakeProvider; Phase 12 workflow)."""

from __future__ import annotations

import os

import pytest
from core.commands.context import CommandContext
from core.runtime.providers.fake_provider import FakeProvider
from tests.fixtures.brownfield_phase12_harness import (
    advance_to_ready_for_change,
    ensure_human_approver,
    recovery_to_baseline,
    run_baseline_stage_workers,
)

pytestmark = [pytest.mark.workflow, pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.asyncio
async def test_brownfield_onboarding_to_ready_for_change(
    db_session,
    system_ctx: CommandContext,
) -> None:
    os.environ["MODEL_PROVIDER"] = "anthropic"
    os.environ["MODEL_DEFAULT"] = "claude-3-5-haiku-20241022"
    os.environ["MODEL_REPOSITORY_REASONING"] = "claude-3-5-haiku-20241022"
    from core.config.settings import clear_settings_cache
    from core.runtime.model_policy import clear_models_config_cache

    clear_settings_cache()
    clear_models_config_cache()

    fake = FakeProvider()
    cycle, _sha = await recovery_to_baseline(db_session, system_ctx, fake=fake)
    await run_baseline_stage_workers(db_session, system_ctx, cycle.id, fake=fake)

    _human, human_ctx = await ensure_human_approver(db_session)
    final = await advance_to_ready_for_change(db_session, cycle.id, system_ctx, human_ctx)
    assert final.state == "READY"
