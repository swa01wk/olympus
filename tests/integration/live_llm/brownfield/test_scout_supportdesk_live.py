"""Phase 11 §11 — live Scout survey + recover_feature on supportdesk_r1."""

from __future__ import annotations

import os
import uuid
from unittest.mock import patch

import pytest
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ExecutionStatus, KnowledgeClass, SpecKind, SpecStatus, TaskStatus
from core.domain.executions.models import Execution
from core.domain.tasks.models import Task
from core.execution.worker import ExecutionWorker
from core.intelligence.brownfield.enums import RecoveryProposalStatus
from core.intelligence.brownfield.models import RecoveryProposal
from core.product_model.models import FeatureSpec, KnowledgeItem
from core.runtime.model_router import build_providers
from core.scheduler.admission import AdmissionService
from core.state.transition_service import TransitionService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from tests.fixtures.brownfield_harness import brownfield_cycle_at_code_index
from tests.fixtures.planning_workflow_harness import ensure_system_actor
from tests.live_credentials import any_live_provider_configured

pytestmark = [pytest.mark.live_llm, pytest.mark.integration, pytest.mark.workflow]


async def _cycle_debug(session: AsyncSession, cycle_id: uuid.UUID) -> str:
    tasks = (
        (await session.execute(select(Task).where(Task.delivery_cycle_id == cycle_id)))
        .scalars()
        .all()
    )
    execs = (
        (await session.execute(select(Execution).where(Execution.delivery_cycle_id == cycle_id)))
        .scalars()
        .all()
    )
    proposals = (
        (
            await session.execute(
                select(RecoveryProposal).where(RecoveryProposal.delivery_cycle_id == cycle_id)
            )
        )
        .scalars()
        .all()
    )
    exec_outputs = [(e.id, list((e.output or {}).keys())[:10]) for e in execs]
    lines = [
        f"tasks={[(t.title, t.status.value) for t in tasks]}",
        f"executions={[(e.id, e.status.value, e.failure_detail) for e in execs]}",
        f"proposals={[(p.status.value, p.validation_report) for p in proposals]}",
        f"exec_output_keys={exec_outputs}",
    ]
    return "; ".join(lines)


@pytest.mark.asyncio
async def test_scout_brownfield_supportdesk_live(async_engine: AsyncEngine) -> None:
    if os.getenv("LLM_LIVE_TESTS") != "1":
        pytest.skip("LLM_LIVE_TESTS=1 required")
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
    project_id: uuid.UUID

    async with factory() as session, session.begin():
        actor = await ensure_system_actor(session)
        setup_ctx = CommandContext(actor=actor, correlation_id="scout-live-setup")
        cycle, _sha, _repo_id = await brownfield_cycle_at_code_index(session, setup_ctx)
        cycle_id = cycle.id
        project_id = cycle.project_id
        await TransitionService().transition(
            session,
            "delivery_cycle",
            cycle_id,
            "CODE_INDEX",
            "start_spec_recovery",
            setup_ctx,
        )

    admission = AdmissionService()
    worker = ExecutionWorker(worker_id=f"scout-live-{uuid.uuid4().hex[:6]}")
    with patch("core.runtime.model_router.build_providers", side_effect=build_providers):
        for round_idx in range(80):
            async with factory() as session, session.begin():
                actor = await ensure_system_actor(session)
                run_ctx = CommandContext(
                    actor=actor,
                    correlation_id=f"scout-live-run-{round_idx}",
                )
                await admission.admit_batch(session, 10, run_ctx)
                for _ in range(10):
                    if not await worker.run_once(session, run_ctx):
                        break
            async with factory() as session:
                proposal_peek = (
                    await session.execute(
                        select(RecoveryProposal).where(
                            RecoveryProposal.delivery_cycle_id == cycle_id,
                            RecoveryProposal.status == RecoveryProposalStatus.VALIDATED,
                        )
                    )
                ).scalar_one_or_none()
                if proposal_peek is not None:
                    break
                open_tasks = (
                    (
                        await session.execute(
                            select(Task).where(
                                Task.delivery_cycle_id == cycle_id,
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
                if not open_tasks:
                    break

        async with factory() as session, session.begin():
            actor = await ensure_system_actor(session)
            finalize_ctx = CommandContext(actor=actor, correlation_id="scout-live-finalize")
            from core.intelligence.recovered_specs.completion import BrownfieldCompletionService

            await BrownfieldCompletionService().try_finalize_recovery(
                session, cycle_id, finalize_ctx
            )

    async with factory() as session:
        proposal = (
            await session.execute(
                select(RecoveryProposal).where(
                    RecoveryProposal.delivery_cycle_id == cycle_id,
                    RecoveryProposal.status == RecoveryProposalStatus.VALIDATED,
                )
            )
        ).scalar_one_or_none()
        if proposal is None:
            debug = await _cycle_debug(session, cycle_id)
            pytest.fail(f"expected VALIDATED recovery proposal after Scout run; {debug}")

        specs = (
            (
                await session.execute(
                    select(FeatureSpec).where(
                        FeatureSpec.project_id == project_id,
                        FeatureSpec.spec_kind == SpecKind.RECOVERED,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert specs, "expected at least one RECOVERED FeatureSpec"
        assert all(s.status == SpecStatus.PROPOSED for s in specs)
        assert all(s.spec_kind != SpecKind.CANONICAL for s in specs)

        facts = (
            (
                await session.execute(
                    select(KnowledgeItem).where(
                        KnowledgeItem.delivery_cycle_id == cycle_id,
                        KnowledgeItem.knowledge_class == KnowledgeClass.FACT,
                    )
                )
            )
            .scalars()
            .all()
        )
        for fact in facts:
            origin = (fact.provenance or {}).get("origin")
            assert origin == "DETERMINISTIC", fact.provenance

        rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        principal_hits = False
        for spec in specs:
            if spec.confidence and spec.claimed_confidence:
                assert rank[spec.confidence] <= rank[spec.claimed_confidence]
            blob = str(spec.body or {})
            if "POST" in blob and "ticket" in blob.lower():
                principal_hits = True
        assert principal_hits, "expected a recovered feature referencing POST /tickets"

        scout_execs = (
            (
                await session.execute(
                    select(Execution).where(Execution.delivery_cycle_id == cycle_id)
                )
            )
            .scalars()
            .all()
        )
        assert any(e.status == ExecutionStatus.COMPLETED for e in scout_execs)

        cycle = await session.get(DeliveryCycle, cycle_id)
        assert cycle is not None
