"""Brownfield onboarding through VALIDATED recovery and start_baseline guard (FakeProvider)."""

from __future__ import annotations

import os
import uuid
from unittest.mock import patch

import pytest
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import KnowledgeClass, TaskStatus
from core.domain.tasks.models import Task
from core.execution.worker import ExecutionWorker
from core.intelligence.brownfield.enums import ObservedBehaviorKind, RecoveryProposalStatus
from core.intelligence.brownfield.models import ObservedBehavior, RecoveryProposal
from core.product_model.models import KnowledgeItem
from core.runtime.providers.fake_provider import FakeProvider, FakeScriptStep
from core.scheduler.admission import AdmissionService
from core.state.transition_service import TransitionService
from sqlalchemy import select
from tests.fixtures.brownfield_harness import brownfield_cycle_at_code_index
from tests.fixtures.brownfield_scout_fake import (
    build_recover_feature_payload,
    build_survey_payload,
)

pytestmark = [pytest.mark.workflow, pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.asyncio
async def test_brownfield_recovery_validated_and_start_baseline_guard(
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

    cycle, _sha, _repo_id = await brownfield_cycle_at_code_index(db_session, system_ctx)
    await TransitionService().transition(
        db_session,
        "delivery_cycle",
        cycle.id,
        "CODE_INDEX",
        "start_spec_recovery",
        system_ctx,
    )

    fake = FakeProvider()
    fake_instance = fake

    def _providers(*, fake=None):
        provider = fake if fake is not None else fake_instance
        return {"anthropic": provider, "openai": provider}

    worker = ExecutionWorker(worker_id=f"bf-wf-{uuid.uuid4().hex[:6]}")
    admission = AdmissionService()

    with patch("core.runtime.model_router.build_providers", side_effect=_providers):
        for round_idx in range(40):
            await admission.admit_batch(db_session, 10, system_ctx)
            for _ in range(10):
                if not await worker.run_once(db_session, system_ctx):
                    break

            behaviors = (
                (
                    await db_session.execute(
                        select(ObservedBehavior).where(
                            ObservedBehavior.delivery_cycle_id == cycle.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            if behaviors and not fake._script:
                behavior_key = next(
                    (
                        b.key
                        for b in behaviors
                        if b.kind == ObservedBehaviorKind.ROUTE_BEHAVIOR
                        and "POST" in (b.description or "")
                    ),
                    behaviors[0].key,
                )
                fact = (
                    (
                        await db_session.execute(
                            select(KnowledgeItem).where(
                                KnowledgeItem.delivery_cycle_id == cycle.id,
                                KnowledgeItem.knowledge_class == KnowledgeClass.FACT,
                            )
                        )
                    )
                    .scalars()
                    .first()
                )
                fact_ref = str(fact.id) if fact else "fact-missing"
                fake.set_script(
                    [
                        FakeScriptStep(
                            structured=build_survey_payload(
                                behavior_key=behavior_key, fact_ref=fact_ref
                            )
                        ),
                        FakeScriptStep(
                            structured=build_recover_feature_payload(behavior_key=behavior_key),
                        ),
                    ]
                )

            proposal_peek = (
                await db_session.execute(
                    select(RecoveryProposal).where(
                        RecoveryProposal.delivery_cycle_id == cycle.id,
                        RecoveryProposal.status == RecoveryProposalStatus.VALIDATED,
                    )
                )
            ).scalar_one_or_none()
            if proposal_peek is not None:
                break
            open_tasks = (
                (
                    await db_session.execute(
                        select(Task).where(
                            Task.delivery_cycle_id == cycle.id,
                            Task.status.notin_(
                                (
                                    TaskStatus.COMPLETED,
                                    TaskStatus.FAILED,
                                    TaskStatus.CANCELLED,
                                )
                            ),
                        )
                    )
                )
                .scalars()
                .all()
            )
            if not open_tasks and round_idx > 5:
                break

    proposal = (
        await db_session.execute(
            select(RecoveryProposal).where(
                RecoveryProposal.delivery_cycle_id == cycle.id,
                RecoveryProposal.status == RecoveryProposalStatus.VALIDATED,
            )
        )
    ).scalar_one_or_none()
    assert proposal is not None

    uncertainties = (
        (
            await db_session.execute(
                select(KnowledgeItem).where(
                    KnowledgeItem.delivery_cycle_id == cycle.id,
                    KnowledgeItem.knowledge_class == KnowledgeClass.UNCERTAINTY,
                )
            )
        )
        .scalars()
        .all()
    )
    assert uncertainties, "expected persisted UNCERTAINTY knowledge items"
    assert all(u.blocking is not None for u in uncertainties)

    refreshed = await db_session.get(DeliveryCycle, cycle.id)
    assert refreshed is not None
    assert refreshed.state == "RECOVERED_SPEC"
    await TransitionService().transition(
        db_session,
        "delivery_cycle",
        cycle.id,
        "RECOVERED_SPEC",
        "start_baseline",
        system_ctx,
    )
    after = await db_session.get(DeliveryCycle, cycle.id)
    assert after is not None
    assert after.state == "BASELINE"
