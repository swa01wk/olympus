"""Deterministic readiness assessment (policy thresholds)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.enums import EvidenceResult
from core.assurance.models import Evidence
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import KnowledgeClass, KnowledgeItemStatus, SpecKind, SpecStatus
from core.domain.events.append import append_domain_event
from core.domain.repositories.models import Repository
from core.integration.enums import SpecCodeLinkOrigin, SpecCodeLinkStatus
from core.intelligence.baselines.enums import BaselineStatus, ReadinessResult
from core.intelligence.baselines.models import (
    BehavioralBaseline,
    PromotionDecision,
    ReadinessAssessment,
)
from core.intelligence.brownfield.enums import ObservedBehaviorKind
from core.intelligence.brownfield.models import ObservedBehavior
from core.intelligence.code_index.enums import EntityType
from core.intelligence.code_index.models import CodeEntity, CodeIndexVersion
from core.planning.models import Architecture
from core.policy.policy_service import PolicyService, ensure_policy_version
from core.product_model.models import FeatureSpec, KnowledgeItem
from core.traceability.models import RepositoryIndexPointer, SpecCodeLink


class ReadinessService:
    async def assess(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
        *,
        recompute: bool = False,
    ) -> ReadinessAssessment:
        if not recompute:
            existing = (
                await session.execute(
                    select(ReadinessAssessment)
                    .where(ReadinessAssessment.delivery_cycle_id == cycle_id)
                    .order_by(ReadinessAssessment.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if existing is not None:
                return existing
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None or cycle.repository_id is None:
            raise ValueError("cycle missing")
        repo = await session.get(Repository, cycle.repository_id)
        if repo is None or repo.canonical_commit is None:
            raise ValueError("repository canonical commit missing")
        commit_sha = repo.canonical_commit
        pointer = await session.get(RepositoryIndexPointer, cycle.repository_id)
        if pointer is None or pointer.canonical_index_version_id is None:
            raise ValueError("canonical index missing")
        index_version = await session.get(CodeIndexVersion, pointer.canonical_index_version_id)
        if index_version is None:
            raise ValueError("index version missing")
        from core.domain.repositories.models import RepositoryRevision

        revision = (
            await session.execute(
                select(RepositoryRevision)
                .where(
                    RepositoryRevision.repository_id == cycle.repository_id,
                    RepositoryRevision.commit_sha == commit_sha,
                )
                .order_by(RepositoryRevision.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if revision is None:
            raise ValueError("canonical revision missing")
        policy = await ensure_policy_version(session)
        thresholds = _readiness_thresholds(policy)
        metrics = await self._compute_metrics(
            session, cycle, commit_sha, index_version.id, thresholds
        )
        reasons = [m["name"] for m in metrics if not m["ok"]]
        result = ReadinessResult.READY if not reasons else ReadinessResult.NOT_READY
        remediable = _classify_remediable(metrics, reasons)
        row = ReadinessAssessment(
            delivery_cycle_id=cycle_id,
            commit_sha=commit_sha,
            index_version_id=index_version.id,
            canonical_revision_id=revision.id,
            metrics=metrics,
            result=result,
            remediable=remediable,
            reasons=reasons,
            policy_version_id=policy.version_row.id if policy.version_row else revision.id,
        )
        session.add(row)
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="delivery_cycle",
            aggregate_id=cycle_id,
            event_type="readiness.assessed",
            payload={"result": result.value, "remediable": remediable},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=cycle.project_id,
            delivery_cycle_id=cycle_id,
        )
        return row

    async def _compute_metrics(
        self,
        session: AsyncSession,
        cycle: DeliveryCycle,
        commit_sha: str,
        index_version_id: uuid.UUID,
        thresholds: dict[str, float],
    ) -> list[dict[str, Any]]:
        principal_coverage = await _metric_principal_coverage(
            session, cycle, index_version_id, thresholds["principal_coverage"]
        )
        review_completion = await _metric_review_completion(
            session, cycle, thresholds["review_completion"]
        )
        baseline_coverage = await _metric_baseline_coverage(
            session, cycle, thresholds["baseline_coverage"]
        )
        baseline_pass = await _metric_baseline_pass(
            session, cycle, commit_sha, thresholds["baseline_pass"]
        )
        blocking_uncertainties = await _metric_blocking_uncertainties(
            session, cycle, thresholds["blocking_uncertainties_open"]
        )
        failing_tests = await _metric_failing_tests(
            session, cycle, thresholds["failing_existing_tests_unclassified"]
        )
        architecture_approved = await _metric_architecture(
            session, cycle, thresholds["architecture_approved"]
        )
        return [
            principal_coverage,
            review_completion,
            baseline_coverage,
            baseline_pass,
            blocking_uncertainties,
            failing_tests,
            architecture_approved,
        ]


def _readiness_thresholds(policy: PolicyService) -> dict[str, float]:
    cfg = policy.get("readiness") or {}
    return {
        "principal_coverage": float(cfg.get("principal_coverage", 0.8)),
        "review_completion": float(cfg.get("review_completion", 1.0)),
        "baseline_coverage": float(cfg.get("baseline_coverage", 1.0)),
        "baseline_pass": float(cfg.get("baseline_pass", 1.0)),
        "blocking_uncertainties_open": float(cfg.get("blocking_uncertainties_open", 0)),
        "failing_existing_tests_unclassified": float(
            cfg.get("failing_existing_tests_unclassified", 0)
        ),
        "architecture_approved": float(cfg.get("architecture_approved", 1.0)),
    }


def _classify_remediable(metrics: list[dict[str, Any]], reasons: list[str]) -> bool:
    if not reasons:
        return False
    remediable_names = {
        "baseline_coverage",
        "principal_coverage",
        "failing_existing_tests_unclassified",
    }
    return all(r in remediable_names for r in reasons)


async def _metric_principal_coverage(
    session: AsyncSession,
    cycle: DeliveryCycle,
    index_version_id: uuid.UUID,
    threshold: float,
) -> dict[str, Any]:
    entities = (
        (
            await session.execute(
                select(CodeEntity).where(
                    CodeEntity.index_version_id == index_version_id,
                    CodeEntity.type.in_((EntityType.ROUTE, EntityType.ORM_MODEL)),
                )
            )
        )
        .scalars()
        .all()
    )
    if not entities:
        return _metric_row("principal_coverage", 1.0, threshold, True)
    covered = 0
    for ent in entities:
        link = (
            await session.execute(
                select(SpecCodeLink)
                .where(
                    SpecCodeLink.project_id == cycle.project_id,
                    SpecCodeLink.code_stable_key == ent.stable_key,
                    SpecCodeLink.status == SpecCodeLinkStatus.ACTIVE,
                    SpecCodeLink.origin.in_(
                        (
                            SpecCodeLinkOrigin.HUMAN_CONFIRMED,
                            SpecCodeLinkOrigin.GENERATED_LINEAGE,
                        )
                    ),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if link is not None:
            covered += 1
    value = covered / len(entities)
    return _metric_row("principal_coverage", value, threshold, value >= threshold)


async def _metric_review_completion(
    session: AsyncSession,
    cycle: DeliveryCycle,
    threshold: float,
) -> dict[str, Any]:
    queue = await _review_subjects(session, cycle)
    if not queue:
        return _metric_row("review_completion", 1.0, threshold, True)
    decided = (
        (
            await session.execute(
                select(PromotionDecision.subject_id).where(
                    PromotionDecision.delivery_cycle_id == cycle.id
                )
            )
        )
        .scalars()
        .all()
    )
    decided_set = set(decided)
    total = len(queue)
    count = sum(1 for sid in queue if sid in decided_set)
    value = count / total
    return _metric_row("review_completion", value, threshold, value >= threshold)


async def _metric_baseline_coverage(
    session: AsyncSession,
    cycle: DeliveryCycle,
    threshold: float,
) -> dict[str, Any]:
    specs = (
        (
            await session.execute(
                select(FeatureSpec).where(
                    FeatureSpec.project_id == cycle.project_id,
                    FeatureSpec.spec_kind == SpecKind.RECOVERED,
                    FeatureSpec.status.in_(
                        (SpecStatus.APPROVED, SpecStatus.PROMOTED, SpecStatus.CONFIRMED_EXISTING)
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    if not specs:
        specs = (
            (
                await session.execute(
                    select(FeatureSpec).where(
                        FeatureSpec.project_id == cycle.project_id,
                        FeatureSpec.spec_kind == SpecKind.CANONICAL,
                        FeatureSpec.status == SpecStatus.APPROVED,
                    )
                )
            )
            .scalars()
            .all()
        )
    if not specs:
        return _metric_row("baseline_coverage", 0.0, threshold, False)
    with_baseline = 0
    for spec in specs:
        bl = (
            await session.execute(
                select(BehavioralBaseline.id)
                .where(
                    BehavioralBaseline.feature_spec_id == spec.id,
                    BehavioralBaseline.status == BaselineStatus.ACTIVE,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if bl is not None:
            with_baseline += 1
    value = with_baseline / len(specs)
    return _metric_row("baseline_coverage", value, threshold, value >= threshold)


async def _metric_baseline_pass(
    session: AsyncSession,
    cycle: DeliveryCycle,
    commit_sha: str,
    threshold: float,
) -> dict[str, Any]:
    baselines = (
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
    if not baselines:
        return _metric_row("baseline_pass", 1.0, threshold, True)
    failing = 0
    for bl in baselines:
        if bl.established_sha != commit_sha:
            failing += 1
            continue
        ev_id = bl.established_evidence_id
        if ev_id is None:
            failing += 1
            continue
        ev = await session.get(Evidence, ev_id)
        if ev is None or ev.result != EvidenceResult.PASS:
            failing += 1
    value = 1.0 - (failing / len(baselines))
    ok = failing == 0 and value >= threshold
    return _metric_row("baseline_pass", value, threshold, ok)


async def _metric_blocking_uncertainties(
    session: AsyncSession,
    cycle: DeliveryCycle,
    threshold: float,
) -> dict[str, Any]:
    open_count = (
        (
            await session.execute(
                select(KnowledgeItem).where(
                    KnowledgeItem.delivery_cycle_id == cycle.id,
                    KnowledgeItem.knowledge_class == KnowledgeClass.UNCERTAINTY,
                    KnowledgeItem.status == KnowledgeItemStatus.ACTIVE,
                )
            )
        )
        .scalars()
        .all()
    )
    blocking = [u for u in open_count if not (u.provenance or {}).get("accepted_known_gap")]
    value = float(len(blocking))
    return _metric_row(
        "blocking_uncertainties_open",
        value,
        threshold,
        value <= threshold,
    )


async def _metric_failing_tests(
    session: AsyncSession,
    cycle: DeliveryCycle,
    threshold: float,
) -> dict[str, Any]:
    fails = (
        (
            await session.execute(
                select(ObservedBehavior).where(
                    ObservedBehavior.delivery_cycle_id == cycle.id,
                    ObservedBehavior.kind == ObservedBehaviorKind.TEST_EXECUTION,
                    ObservedBehavior.passed.is_(False),
                )
            )
        )
        .scalars()
        .all()
    )
    unclassified = [f for f in fails if not (f.evidence_refs or [])]
    value = float(len(unclassified))
    return _metric_row(
        "failing_existing_tests_unclassified",
        value,
        threshold,
        value <= threshold,
    )


async def _metric_architecture(
    session: AsyncSession,
    cycle: DeliveryCycle,
    threshold: float,
) -> dict[str, Any]:
    arch = (
        await session.execute(
            select(Architecture)
            .where(
                Architecture.project_id == cycle.project_id,
                Architecture.kind == "RECOVERED",
            )
            .order_by(Architecture.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    approved = arch is not None and arch.status == SpecStatus.APPROVED
    value = 1.0 if approved else 0.0
    return _metric_row("architecture_approved", value, threshold, approved)


def _metric_row(name: str, value: float, threshold: float, ok: bool) -> dict[str, Any]:
    return {"name": name, "value": value, "threshold": threshold, "ok": ok}


async def _review_subjects(session: AsyncSession, cycle: DeliveryCycle) -> list[uuid.UUID]:
    subjects: list[uuid.UUID] = []
    specs = (
        (
            await session.execute(
                select(FeatureSpec.id).where(
                    FeatureSpec.project_id == cycle.project_id,
                    FeatureSpec.spec_kind == SpecKind.RECOVERED,
                    FeatureSpec.status == SpecStatus.PROPOSED,
                )
            )
        )
        .scalars()
        .all()
    )
    subjects.extend(specs)
    baselines = (
        (
            await session.execute(
                select(BehavioralBaseline.id).where(
                    BehavioralBaseline.project_id == cycle.project_id,
                    BehavioralBaseline.status == BaselineStatus.PROPOSED,
                )
            )
        )
        .scalars()
        .all()
    )
    subjects.extend(baselines)
    arch = (
        await session.execute(
            select(Architecture.id)
            .where(
                Architecture.project_id == cycle.project_id,
                Architecture.kind == "RECOVERED",
                Architecture.status == SpecStatus.PROPOSED,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if arch:
        subjects.append(arch)
    return subjects
