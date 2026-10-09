"""A REJECTED recovery proposal can be retried from RECOVERED_SPEC (FakeProvider)."""

from __future__ import annotations

import os
import uuid
from unittest.mock import patch

import pytest
from core.commands.context import CommandContext
from core.domain.enums import KnowledgeClass
from core.domain.exceptions import GuardFailed
from core.execution.worker import ExecutionWorker
from core.intelligence.brownfield.enums import ObservedBehaviorKind, RecoveryProposalStatus
from core.intelligence.brownfield.models import ObservedBehavior, RecoveryProposal
from core.product_model.models import KnowledgeItem
from core.runtime.providers.fake_provider import FakeProvider, FakeScriptStep
from core.scheduler.admission import AdmissionService
from core.state.preview import TransitionPreviewService
from core.state.transition_service import TransitionService
from sqlalchemy import select
from tests.fixtures.brownfield_harness import brownfield_cycle_at_code_index
from tests.fixtures.brownfield_scout_fake import (
    build_recover_feature_payload,
    build_survey_payload,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _fake_env() -> None:
    os.environ["MODEL_PROVIDER"] = "anthropic"
    os.environ["MODEL_DEFAULT"] = "claude-3-5-haiku-20241022"
    os.environ["MODEL_REPOSITORY_REASONING"] = "claude-3-5-haiku-20241022"
    from core.config.settings import clear_settings_cache
    from core.runtime.model_policy import clear_models_config_cache

    clear_settings_cache()
    clear_models_config_cache()


async def _drain_recovery(
    session,
    ctx: CommandContext,
    cycle_id: uuid.UUID,
    fake: FakeProvider,
    *,
    ac_behavior_key: str | None,
    expected_proposals: int,
) -> None:
    """Run workers; once behaviours exist, script one Scout survey + feature recovery."""
    worker = ExecutionWorker(worker_id=f"bf-retry-{uuid.uuid4().hex[:6]}")
    admission = AdmissionService()
    scripted = False

    def _providers(**_kwargs):
        return {"anthropic": fake, "openai": fake}

    with patch("core.runtime.model_router.build_providers", side_effect=_providers):
        for _ in range(30):
            await admission.admit_batch(session, 10, ctx)
            for _ in range(10):
                await worker.run_once(session, ctx)
            behaviors = (
                (
                    await session.execute(
                        select(ObservedBehavior).where(
                            ObservedBehavior.delivery_cycle_id == cycle_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            if behaviors and not scripted:
                route = next(
                    b.key
                    for b in behaviors
                    if b.kind == ObservedBehaviorKind.ROUTE_BEHAVIOR and "POST" in b.description
                )
                fact = (
                    (
                        await session.execute(
                            select(KnowledgeItem).where(
                                KnowledgeItem.delivery_cycle_id == cycle_id,
                                KnowledgeItem.knowledge_class == KnowledgeClass.FACT,
                            )
                        )
                    )
                    .scalars()
                    .first()
                )
                fake.set_script(
                    [
                        FakeScriptStep(
                            structured=build_survey_payload(
                                behavior_key=route, fact_ref=str(fact.id) if fact else "f"
                            )
                        ),
                        FakeScriptStep(
                            structured=build_recover_feature_payload(
                                behavior_key=ac_behavior_key or route
                            )
                        ),
                    ]
                )
                scripted = True
            if scripted and not fake._script:
                count = len(
                    (
                        await session.execute(
                            select(RecoveryProposal.id).where(
                                RecoveryProposal.delivery_cycle_id == cycle_id
                            )
                        )
                    ).all()
                )
                if count >= expected_proposals:
                    return


async def _proposals(session, cycle_id: uuid.UUID) -> list[RecoveryProposal]:
    return list(
        (
            await session.execute(
                select(RecoveryProposal)
                .where(RecoveryProposal.delivery_cycle_id == cycle_id)
                .order_by(RecoveryProposal.created_at)
            )
        )
        .scalars()
        .all()
    )


async def test_rejected_recovery_retried_to_validated(
    db_session,
    system_ctx: CommandContext,
) -> None:
    _fake_env()
    cycle, _sha, _repo_id = await brownfield_cycle_at_code_index(db_session, system_ctx)
    transitions = TransitionService()
    await transitions.transition(
        db_session, "delivery_cycle", cycle.id, "CODE_INDEX", "start_spec_recovery", system_ctx
    )

    fake = FakeProvider()
    await _drain_recovery(
        db_session, system_ctx, cycle.id, fake, ac_behavior_key="OB-9999", expected_proposals=1
    )
    [rejected] = await _proposals(db_session, cycle.id)
    assert rejected.status == RecoveryProposalStatus.REJECTED
    assert "NO_SUPPORTED_FEATURES" in rejected.validation_report["errors"]
    assert any(p["removed"] == "feature" for p in rejected.validation_report["pruned"])

    previews = {
        p.command: p
        for p in await TransitionPreviewService().preview(
            db_session, "delivery_cycle", cycle.id, system_ctx
        )
    }
    assert previews["retry_spec_recovery"].allowed
    assert not previews["start_baseline"].allowed
    with pytest.raises(GuardFailed):
        await transitions.transition(
            db_session, "delivery_cycle", cycle.id, "RECOVERED_SPEC", "start_baseline", system_ctx
        )

    await transitions.transition(
        db_session, "delivery_cycle", cycle.id, "RECOVERED_SPEC", "retry_spec_recovery", system_ctx
    )
    previews = {
        p.command: p
        for p in await TransitionPreviewService().preview(
            db_session, "delivery_cycle", cycle.id, system_ctx
        )
    }
    assert not previews["retry_spec_recovery"].allowed, "retry closes while Scout re-runs"

    await _drain_recovery(
        db_session, system_ctx, cycle.id, fake, ac_behavior_key=None, expected_proposals=2
    )
    proposals = await _proposals(db_session, cycle.id)
    assert [p.status for p in proposals] == [
        RecoveryProposalStatus.REJECTED,
        RecoveryProposalStatus.VALIDATED,
    ]
    await transitions.transition(
        db_session, "delivery_cycle", cycle.id, "RECOVERED_SPEC", "start_baseline", system_ctx
    )
