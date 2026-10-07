"""Phase 12 §12 — promotion decisions and declare_ready persistence (deterministic)."""

from __future__ import annotations

import os
import uuid

import pytest
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind, ActorRole, SpecKind, SpecStatus
from core.domain.exceptions import Unauthorized
from core.intelligence.baselines.models import BaselineSet
from core.intelligence.recovered_specs.promotion import PromotionService
from core.product_model.models import FeatureSpec
from core.runtime.providers.fake_provider import FakeProvider
from sqlalchemy import select
from tests.fixtures.brownfield_phase12_harness import (
    _activate_eligible_baselines,
    _declare_ready_with_workflow_thresholds,
    apply_brownfield_review_decisions,
    ensure_human_approver,
    recovery_to_baseline,
    run_baseline_stage_workers,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.asyncio
async def test_promotion_without_approver_role_rejected(
    db_session,
    system_ctx: CommandContext,
) -> None:
    os.environ["MODEL_PROVIDER"] = "anthropic"
    os.environ["MODEL_DEFAULT"] = "claude-3-5-haiku-20241022"
    from core.config.settings import clear_settings_cache
    from core.runtime.model_policy import clear_models_config_cache

    clear_settings_cache()
    clear_models_config_cache()

    fake = FakeProvider()
    cycle, _sha = await recovery_to_baseline(db_session, system_ctx, fake=fake)
    recovered = (
        await db_session.execute(
            select(FeatureSpec).where(
                FeatureSpec.project_id == cycle.project_id,
                FeatureSpec.spec_kind == SpecKind.RECOVERED,
            )
        )
    ).scalar_one()
    operator = Actor(
        kind=ActorKind.HUMAN,
        name=f"no-approver-{uuid.uuid4().hex[:6]}",
        roles=[ActorRole.OPERATOR.value],
    )
    db_session.add(operator)
    await db_session.flush()
    op_ctx = CommandContext(actor=operator, correlation_id="promotion-403")
    with pytest.raises(Unauthorized):
        await PromotionService().decide(
            db_session,
            cycle.id,
            "FEATURE_SPEC",
            recovered.id,
            "PROMOTE_AS_CANONICAL",
            None,
            op_ctx,
        )


@pytest.mark.asyncio
async def test_reject_promotion_does_not_create_canonical_spec(
    db_session,
    system_ctx: CommandContext,
) -> None:
    os.environ["MODEL_PROVIDER"] = "anthropic"
    os.environ["MODEL_DEFAULT"] = "claude-3-5-haiku-20241022"
    from core.config.settings import clear_settings_cache
    from core.runtime.model_policy import clear_models_config_cache

    clear_settings_cache()
    clear_models_config_cache()

    fake = FakeProvider()
    cycle, _sha = await recovery_to_baseline(db_session, system_ctx, fake=fake)
    recovered = (
        await db_session.execute(
            select(FeatureSpec).where(
                FeatureSpec.project_id == cycle.project_id,
                FeatureSpec.spec_kind == SpecKind.RECOVERED,
            )
        )
    ).scalar_one()
    _human, human_ctx = await ensure_human_approver(db_session)
    await PromotionService().decide(
        db_session,
        cycle.id,
        "FEATURE_SPEC",
        recovered.id,
        "REJECT_AS_NOT_INTENDED",
        "not intended behavior",
        human_ctx,
    )
    canonical = (
        await db_session.execute(
            select(FeatureSpec).where(
                FeatureSpec.project_id == cycle.project_id,
                FeatureSpec.spec_kind == SpecKind.CANONICAL,
            )
        )
    ).scalar_one_or_none()
    assert canonical is None
    await db_session.refresh(recovered)
    assert recovered.status == SpecStatus.REJECTED


@pytest.mark.asyncio
async def test_declare_ready_creates_baseline_set(
    db_session,
    system_ctx: CommandContext,
) -> None:
    os.environ["MODEL_PROVIDER"] = "anthropic"
    os.environ["MODEL_DEFAULT"] = "claude-3-5-haiku-20241022"
    from core.config.settings import clear_settings_cache
    from core.runtime.model_policy import clear_models_config_cache

    clear_settings_cache()
    clear_models_config_cache()

    fake = FakeProvider()
    cycle, _sha = await recovery_to_baseline(db_session, system_ctx, fake=fake)
    await run_baseline_stage_workers(db_session, system_ctx, cycle.id, fake=fake)
    _human, human_ctx = await ensure_human_approver(db_session)
    await apply_brownfield_review_decisions(db_session, cycle.id, human_ctx)
    await _activate_eligible_baselines(db_session, cycle.id, human_ctx)
    from core.state.transition_service import TransitionService

    await TransitionService().transition(
        db_session,
        "delivery_cycle",
        cycle.id,
        "BASELINE",
        "start_readiness",
        system_ctx,
    )
    await _declare_ready_with_workflow_thresholds(db_session, cycle.id, system_ctx)
    bsets = (
        await db_session.execute(
            select(BaselineSet).where(BaselineSet.delivery_cycle_id == cycle.id)
        )
    ).scalars()
    assert len(list(bsets)) == 1
