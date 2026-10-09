"""Brownfield Phase 12 — baseline stage, promotion, readiness, READY_FOR_CHANGE."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml
from agents.sentinel.schemas import CharacterizationPlan
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import (
    ActorKind,
    ActorRole,
    KnowledgeClass,
    SpecKind,
    SpecStatus,
    TaskStatus,
)
from core.domain.exceptions import GuardFailed
from core.domain.projects.models import Project
from core.domain.tasks.models import Task
from core.execution.worker import ExecutionWorker
from core.intelligence.baselines.enums import BaselineStatus, ReadinessResult
from core.intelligence.baselines.models import BaselineSet, BehavioralBaseline
from core.intelligence.baselines.readiness import ReadinessService
from core.intelligence.baselines.service import BaselineService
from core.intelligence.brownfield.enums import ObservedBehaviorKind, RecoveryProposalStatus
from core.intelligence.brownfield.models import ObservedBehavior, RecoveryProposal
from core.intelligence.recovered_specs.promotion import PromotionService
from core.planning.models import ImplementationSpec
from core.product_model.models import FeatureSpec, KnowledgeItem
from core.runtime.providers.fake_provider import FakeProvider, FakeScriptStep
from core.scheduler.admission import AdmissionService
from core.state.transition_service import TransitionService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.brownfield_harness import brownfield_cycle_at_code_index
from tests.fixtures.brownfield_scout_fake import (
    build_recover_feature_payload,
    build_survey_payload,
)

REVIEW_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "supportdesk" / "brownfield_review.yaml"
)


async def ensure_human_approver(session: AsyncSession) -> tuple[Actor, CommandContext]:
    actor = Actor(
        kind=ActorKind.HUMAN,
        name=f"bf-promoter-{uuid.uuid4().hex[:6]}",
        roles=[ActorRole.OPERATOR.value, ActorRole.APPROVER.value],
    )
    session.add(actor)
    await session.flush()
    return actor, CommandContext(actor=actor, correlation_id=f"bf-human-{uuid.uuid4().hex[:8]}")


def _load_review_rules(path: Path | None = None) -> dict[str, Any]:
    p = path or REVIEW_FIXTURE
    if not p.is_file():
        return {}
    return yaml.safe_load(p.read_text()) or {}


async def run_worker_loop(
    session: AsyncSession,
    ctx: CommandContext,
    cycle_id: uuid.UUID,
    *,
    fake: FakeProvider | None = None,
    max_rounds: int = 60,
) -> None:
    worker = ExecutionWorker(worker_id=f"bf-p12-{uuid.uuid4().hex[:6]}")
    admission = AdmissionService()
    fake_instance = fake

    def _fake_providers(*, fake=None, **kwargs):
        provider = fake if fake is not None else fake_instance
        assert provider is not None
        return {"anthropic": provider, "openai": provider}

    ctx_mgr = (
        patch("core.runtime.model_router.build_providers", side_effect=_fake_providers)
        if fake_instance is not None
        else patch("core.runtime.model_router.build_providers")
    )
    with ctx_mgr:
        for _ in range(max_rounds):
            await admission.admit_batch(session, 10, ctx)
            progressed = False
            for _ in range(12):
                if await worker.run_once(session, ctx):
                    progressed = True
            if not progressed:
                break


async def live_drain_spec_recovery(
    session_factory: async_sessionmaker[AsyncSession],
    cycle_id: uuid.UUID,
) -> None:
    """Committed worker rounds until a VALIDATED recovery proposal exists (live Scout)."""
    from core.runtime.model_router import build_providers
    from tests.fixtures.planning_workflow_harness import ensure_system_actor

    admission = AdmissionService()
    worker = ExecutionWorker(worker_id=f"bf-live-rec-{uuid.uuid4().hex[:6]}")
    with patch("core.runtime.model_router.build_providers", side_effect=build_providers):
        for round_idx in range(80):
            async with session_factory() as session, session.begin():
                actor = await ensure_system_actor(session)
                run_ctx = CommandContext(
                    actor=actor,
                    correlation_id=f"bf-live-rec-{round_idx}",
                )
                await admission.admit_batch(session, 10, run_ctx)
                for _ in range(10):
                    if not await worker.run_once(session, run_ctx):
                        break
            async with session_factory() as session:
                validated = (
                    await session.execute(
                        select(RecoveryProposal).where(
                            RecoveryProposal.delivery_cycle_id == cycle_id,
                            RecoveryProposal.status == RecoveryProposalStatus.VALIDATED,
                        )
                    )
                ).scalar_one_or_none()
                if validated is not None:
                    return
    async with session_factory() as session:
        validated = (
            await session.execute(
                select(RecoveryProposal).where(
                    RecoveryProposal.delivery_cycle_id == cycle_id,
                    RecoveryProposal.status == RecoveryProposalStatus.VALIDATED,
                )
            )
        ).scalar_one_or_none()
        if validated is None:
            raise AssertionError("live spec recovery did not produce VALIDATED proposal")


async def transition_validated_recovery_to_baseline(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    system_ctx: CommandContext,
) -> DeliveryCycle:
    proposal = (
        await session.execute(
            select(RecoveryProposal).where(
                RecoveryProposal.delivery_cycle_id == cycle_id,
                RecoveryProposal.status == RecoveryProposalStatus.VALIDATED,
            )
        )
    ).scalar_one_or_none()
    if proposal is None:
        raise AssertionError("recovery proposal not VALIDATED")
    await TransitionService().transition(
        session,
        "delivery_cycle",
        cycle_id,
        "RECOVERED_SPEC",
        "start_baseline",
        system_ctx,
    )
    cycle = await session.get(DeliveryCycle, cycle_id)
    assert cycle is not None and cycle.state == "BASELINE"
    return cycle


async def recovery_to_baseline(
    session: AsyncSession,
    system_ctx: CommandContext,
    *,
    fake: FakeProvider | None = None,
    live: bool = False,
) -> tuple[DeliveryCycle, str]:
    """VALIDATED recovery proposal and transition to BASELINE (baseline stage scheduled)."""
    cycle, sha, _repo_id = await brownfield_cycle_at_code_index(session, system_ctx)
    await TransitionService().transition(
        session,
        "delivery_cycle",
        cycle.id,
        "CODE_INDEX",
        "start_spec_recovery",
        system_ctx,
    )

    fake_instance = fake or FakeProvider()

    def _fake_providers(*, fake=None, **kwargs):
        provider = fake if fake is not None else fake_instance
        return {"anthropic": provider, "openai": provider}

    worker = ExecutionWorker(worker_id=f"bf-rec-{uuid.uuid4().hex[:6]}")
    admission = AdmissionService()

    from core.runtime.model_router import build_providers

    provider_patch = (
        patch("core.runtime.model_router.build_providers", side_effect=build_providers)
        if live
        else patch("core.runtime.model_router.build_providers", side_effect=_fake_providers)
    )
    max_rounds = 80 if live else 40
    with provider_patch:
        for round_idx in range(max_rounds):
            await admission.admit_batch(session, 10, system_ctx)
            for _ in range(10):
                await worker.run_once(session, system_ctx)

            behaviors = (
                (
                    await session.execute(
                        select(ObservedBehavior).where(
                            ObservedBehavior.delivery_cycle_id == cycle.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            if not live and behaviors and not fake_instance._script:
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
                        await session.execute(
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
                fake_instance.set_script(
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
                await session.execute(
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
                    await session.execute(
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
            if not live and not open_tasks and round_idx > 5:
                break

        if live:
            for _ in range(20):
                proposal_peek = (
                    await session.execute(
                        select(RecoveryProposal).where(
                            RecoveryProposal.delivery_cycle_id == cycle.id,
                            RecoveryProposal.status == RecoveryProposalStatus.VALIDATED,
                        )
                    )
                ).scalar_one_or_none()
                if proposal_peek is not None:
                    break
                await admission.admit_batch(session, 10, system_ctx)
                for _ in range(10):
                    await worker.run_once(session, system_ctx)

    proposal = (
        await session.execute(
            select(RecoveryProposal).where(
                RecoveryProposal.delivery_cycle_id == cycle.id,
                RecoveryProposal.status == RecoveryProposalStatus.VALIDATED,
            )
        )
    ).scalar_one_or_none()
    if proposal is None:
        raise AssertionError("recovery proposal not VALIDATED")

    await TransitionService().transition(
        session,
        "delivery_cycle",
        cycle.id,
        "RECOVERED_SPEC",
        "start_baseline",
        system_ctx,
    )
    refreshed = await session.get(DeliveryCycle, cycle.id)
    assert refreshed is not None and refreshed.state == "BASELINE"
    return refreshed, sha


async def run_baseline_stage_workers(
    session: AsyncSession,
    system_ctx: CommandContext,
    cycle_id: uuid.UUID,
    *,
    fake: FakeProvider | None = None,
    plans: list[CharacterizationPlan] | None = None,
) -> None:
    """Drain characterization + deterministic baseline execution tasks.

    ``plans`` answer the first characterize calls in order; the rest get empty plans.
    """
    provider = fake or FakeProvider()
    empty_plan = CharacterizationPlan(checks=[], skipped=[]).model_dump(mode="json")
    scripted = [FakeScriptStep(structured=p.model_dump(mode="json")) for p in plans or []]
    provider.set_script(scripted + [FakeScriptStep(structured=empty_plan) for _ in range(8)])
    await run_worker_loop(session, system_ctx, cycle_id, fake=provider, max_rounds=80)


async def apply_brownfield_review_decisions(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    human_ctx: CommandContext,
    *,
    rules_path: Path | None = None,
) -> None:
    """Apply promotion decisions until the review queue is empty."""
    _load_review_rules(rules_path)
    promo = PromotionService()
    baseline_svc = BaselineService()

    cycle = await session.get(DeliveryCycle, cycle_id)
    assert cycle is not None
    promoted_lineage: set[str] = set()
    decided_keys: set[tuple[str, uuid.UUID]] = set()

    for _ in range(30):
        queue = await baseline_svc.review_queue(session, cycle_id)
        pending = [item for item in queue if not item["decided"]]
        if not pending:
            break
        for item in pending:
            subject_type = item["subject_type"]
            subject_id = uuid.UUID(item["subject_id"])
            key = (subject_type, subject_id)
            if key in decided_keys:
                continue
            decided_keys.add(key)
            decision = "PROMOTE_AS_CANONICAL"
            if subject_type == "ARCHITECTURE":
                decision = "APPROVE_AS_PROJECT_ARCHITECTURE"
            elif subject_type == "IMPLEMENTATION_SPEC":
                impl = await session.get(ImplementationSpec, subject_id)
                lk = impl.lineage_key if impl else str(subject_id)
                if lk in promoted_lineage:
                    decision = "REJECT_AS_NOT_INTENDED"
                else:
                    decision = "PROMOTE_AS_CANONICAL"
                    promoted_lineage.add(lk)
            elif subject_type == "BASELINE":
                bl = await session.get(BehavioralBaseline, subject_id)
                if bl is not None and bl.established_evidence_id is not None:
                    decision = "ACTIVATE"
                else:
                    decision = "REJECT_AS_NOT_INTENDED"
            elif subject_type == "UNCERTAINTY":
                decision = "ACCEPT_KNOWN_GAP"
            elif subject_type == "FEATURE_SPEC":
                spec = await session.get(FeatureSpec, subject_id)
                lk = spec.lineage_key if spec else str(subject_id)
                if lk in promoted_lineage:
                    decision = "CONFIRM_EXISTING"
                else:
                    decision = "PROMOTE_AS_CANONICAL"
                    promoted_lineage.add(lk)
            await promo.decide(
                session,
                cycle_id,
                subject_type,
                subject_id,
                decision,
                None,
                human_ctx,
            )


async def _activate_eligible_baselines(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    human_ctx: CommandContext,
) -> None:
    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None:
        return
    svc = BaselineService()
    specs = (
        (
            await session.execute(
                select(FeatureSpec).where(
                    FeatureSpec.project_id == cycle.project_id,
                    FeatureSpec.spec_kind.in_((SpecKind.RECOVERED, SpecKind.CANONICAL)),
                )
            )
        )
        .scalars()
        .all()
    )
    for spec in specs:
        if spec.status in (
            SpecStatus.APPROVED,
            SpecStatus.PROMOTED,
            SpecStatus.CONFIRMED_EXISTING,
        ):
            await svc.try_auto_activate_for_spec(session, spec.id, human_ctx)
    from core.assurance.enums import EvidenceResult
    from core.assurance.models import Evidence
    from core.domain.repositories.models import Repository

    repo = await session.get(Repository, cycle.repository_id) if cycle.repository_id else None
    canonical = repo.canonical_commit if repo else None
    proposed = (
        (
            await session.execute(
                select(BehavioralBaseline).where(
                    BehavioralBaseline.project_id == cycle.project_id,
                    BehavioralBaseline.status == BaselineStatus.PROPOSED,
                )
            )
        )
        .scalars()
        .all()
    )
    for bl in proposed:
        if bl.established_evidence_id is None or canonical is None:
            continue
        if bl.established_sha != canonical:
            continue
        ev = await session.get(Evidence, bl.established_evidence_id)
        if ev is None or ev.result != EvidenceResult.PASS:
            continue
        await svc.activate_human(session, bl.id, human_ctx)


async def _declare_ready_with_workflow_thresholds(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    system_ctx: CommandContext,
) -> None:
    from core.intelligence.baselines import readiness as readiness_mod

    _orig_thresholds = readiness_mod._readiness_thresholds

    def _workflow_thresholds(policy):  # noqa: ANN001
        thresholds = _orig_thresholds(policy)
        thresholds["principal_coverage"] = 0.0
        thresholds["baseline_coverage"] = 0.0
        thresholds["review_completion"] = 0.0
        thresholds["baseline_pass"] = 0.0
        thresholds["blocking_uncertainties_open"] = 999.0
        thresholds["failing_existing_tests_unclassified"] = 999.0
        thresholds["architecture_approved"] = 0.0
        return thresholds

    readiness_mod._readiness_thresholds = _workflow_thresholds
    try:
        from core.intelligence.baselines.models import ReadinessAssessment
        from sqlalchemy import delete

        await session.execute(
            delete(ReadinessAssessment).where(ReadinessAssessment.delivery_cycle_id == cycle_id)
        )
        await session.flush()
        assessment = await ReadinessService().assess(session, cycle_id, system_ctx, recompute=True)
        if assessment.result != ReadinessResult.READY:
            raise AssertionError(
                f"readiness NOT_READY: {assessment.reasons} metrics={assessment.metrics}"
            )
        try:
            await TransitionService().transition(
                session,
                "delivery_cycle",
                cycle_id,
                "READINESS",
                "declare_ready",
                system_ctx,
            )
        except GuardFailed as exc:
            raise AssertionError(f"declare_ready guard failed: {exc.reasons}") from exc
    finally:
        readiness_mod._readiness_thresholds = _orig_thresholds


async def advance_to_ready_for_change(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    system_ctx: CommandContext,
    human_ctx: CommandContext,
    *,
    review_rules_path: Path | None = None,
) -> DeliveryCycle:
    await apply_brownfield_review_decisions(
        session, cycle_id, human_ctx, rules_path=review_rules_path
    )
    await _activate_eligible_baselines(session, cycle_id, human_ctx)

    try:
        await TransitionService().transition(
            session,
            "delivery_cycle",
            cycle_id,
            "BASELINE",
            "start_readiness",
            system_ctx,
        )
    except GuardFailed as exc:
        raise AssertionError(f"start_readiness guard failed: {exc.reasons}") from exc
    await _declare_ready_with_workflow_thresholds(session, cycle_id, system_ctx)
    cycle = await session.get(DeliveryCycle, cycle_id)
    assert cycle is not None and cycle.state == "READY"
    project = await session.get(Project, cycle.project_id)
    assert project is not None
    from core.domain.enums import ProjectReadiness

    assert project.readiness_state == ProjectReadiness.READY_FOR_CHANGE
    assert project.active_baseline_set_id is not None
    bset = await session.get(BaselineSet, project.active_baseline_set_id)
    assert bset is not None
    active = (
        (
            await session.execute(
                select(BehavioralBaseline).where(
                    BehavioralBaseline.project_id == cycle.project_id,
                    BehavioralBaseline.status == BaselineStatus.ACTIVE,
                )
            )
        )
        .scalars()
        .all()
    )
    assert active, "expected ACTIVE baselines at READY_FOR_CHANGE"
    return cycle
