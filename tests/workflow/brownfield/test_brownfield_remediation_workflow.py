"""NOT_READY → REMEDIATION → release → reassess → READY_FOR_CHANGE (Phase 12 AC)."""

from __future__ import annotations

import os

import pytest
from core.commands.context import CommandContext
from core.domain.exceptions import GuardFailed
from core.intelligence.baselines.enums import ReadinessResult
from core.intelligence.baselines.readiness import ReadinessService
from core.runtime.providers.fake_provider import FakeProvider
from core.state.transition_service import TransitionService
from tests.fixtures.brownfield_phase12_harness import (
    _activate_eligible_baselines,
    _declare_ready_with_workflow_thresholds,
    apply_brownfield_review_decisions,
    ensure_human_approver,
    recovery_to_baseline,
    run_baseline_stage_workers,
)
from tests.fixtures.brownfield_remediation_harness import run_brownfield_remediation_loop

pytestmark = [pytest.mark.workflow, pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.asyncio
async def test_brownfield_remediation_readiness_to_ready(
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
    _human, human_ctx = await ensure_human_approver(db_session)
    await apply_brownfield_review_decisions(db_session, cycle.id, human_ctx)

    try:
        await TransitionService().transition(
            db_session,
            "delivery_cycle",
            cycle.id,
            "BASELINE",
            "start_readiness",
            system_ctx,
        )
    except GuardFailed as exc:
        raise AssertionError(f"start_readiness: {exc.reasons}") from exc

    assessment = await ReadinessService().assess(db_session, cycle.id, system_ctx, recompute=True)
    assert assessment.result == ReadinessResult.NOT_READY
    assert assessment.remediable is True

    await TransitionService().transition(
        db_session,
        "delivery_cycle",
        cycle.id,
        "READINESS",
        "start_remediation",
        system_ctx,
    )

    await run_brownfield_remediation_loop(db_session, cycle.id, system_ctx, human_ctx)

    await TransitionService().transition(
        db_session,
        "delivery_cycle",
        cycle.id,
        "REMEDIATION",
        "reassess_readiness",
        system_ctx,
    )

    await run_baseline_stage_workers(db_session, system_ctx, cycle.id, fake=fake)
    await apply_brownfield_review_decisions(db_session, cycle.id, human_ctx)
    await _activate_eligible_baselines(db_session, cycle.id, human_ctx)

    await _declare_ready_with_workflow_thresholds(db_session, cycle.id, system_ctx)
    from core.domain.delivery_cycles.models import DeliveryCycle

    refreshed = await db_session.get(DeliveryCycle, cycle.id)
    assert refreshed is not None and refreshed.state == "READY"
