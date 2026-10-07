"""Deterministic release eligibility evaluation and condition registry."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.enums import EvidenceResult, ObligationStatus
from core.assurance.evidence_rules import evidence_satisfies_mandatory
from core.assurance.models import AcceptanceCoverage, Evidence, Finding, VerificationObligation
from core.commands.context import CommandContext
from core.domain.candidate_commits.models import CandidateCommit
from core.domain.canonical_json import sha256_hex
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import (
    DeliveryCycleType,
    ExecutionStatus,
    TaskStatus,
    WorkType,
)
from core.domain.executions.models import Execution
from core.domain.repositories.models import Repository
from core.domain.tasks.models import Task
from core.integration.enums import FindingStatus, ICStatus
from core.integration.models import IntegrationCandidate, IntegrationCandidateCommit
from core.policy.policy_service import ensure_policy_version, get_cached_policy_content
from core.release.manifest import ManifestBuilder, validate_manifest_against_ic
from core.release.models import Release, ReleaseEligibilityEvaluation
from core.release.schemas import ReleaseManifestContent

ConditionFn = Callable[
    [AsyncSession, DeliveryCycle, IntegrationCandidate | None, Release | None, dict[str, Any]],
    Awaitable["ConditionResult"],
]


@dataclass(frozen=True)
class ConditionResult:
    name: str
    ok: bool
    reasons: tuple[str, ...]
    inputs_hash: str


class EligibilityConditionRegistry:
    def __init__(self) -> None:
        self._conditions: dict[str, ConditionFn] = {}

    def register(self, name: str, fn: ConditionFn) -> None:
        self._conditions[name] = fn

    def get(self, name: str) -> ConditionFn | None:
        return self._conditions.get(name)


_registry = EligibilityConditionRegistry()


def get_eligibility_registry() -> EligibilityConditionRegistry:
    return _registry


def _default_required_conditions(cycle_type: DeliveryCycleType) -> list[str]:
    policy = get_cached_policy_content().get("release", {})
    by_type = policy.get("eligibility_conditions", {})
    default = [
        "manifest_valid",
        "integration_candidate_is_current",
        "required_gates_pass",
        "required_approvals_exist",
        "required_executions_not_stale",
        "blocking_findings",
        "mandatory_acceptance_criteria_have_evidence",
        "required_behavioral_baselines_pass",
    ]
    return list(by_type.get(cycle_type.value, by_type.get("default", default)))


async def _cond_manifest_valid(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ic: IntegrationCandidate | None,
    release: Release | None,
    _inputs: dict[str, Any],
) -> ConditionResult:
    name = "manifest_valid"
    if release is None or release.manifest_id is None or ic is None:
        return ConditionResult(name, False, ("RELEASE_OR_MANIFEST_MISSING",), sha256_hex({}))
    manifest_row = await ManifestBuilder().load_manifest(session, release.manifest_id)
    if manifest_row is None:
        return ConditionResult(name, False, ("MANIFEST_NOT_FOUND",), sha256_hex({}))
    try:
        content = ReleaseManifestContent.model_validate(manifest_row.content)
    except Exception as exc:
        return ConditionResult(name, False, (f"MANIFEST_INVALID:{exc}",), sha256_hex({}))
    ok, reasons = validate_manifest_against_ic(content, ic, cycle)
    return ConditionResult(name, ok, tuple(reasons), sha256_hex(content.model_dump(mode="json")))


async def _cond_ic_current(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ic: IntegrationCandidate | None,
    _release: Release | None,
    _inputs: dict[str, Any],
) -> ConditionResult:
    name = "integration_candidate_is_current"
    if ic is None:
        return ConditionResult(name, False, ("IC_MISSING",), sha256_hex({}))
    if ic.status != ICStatus.READY:
        return ConditionResult(name, False, (f"IC_NOT_READY:{ic.status.value}",), sha256_hex({}))
    latest = await session.execute(
        select(IntegrationCandidate)
        .where(
            IntegrationCandidate.delivery_cycle_id == cycle.id,
            IntegrationCandidate.status == ICStatus.READY,
        )
        .order_by(IntegrationCandidate.created_at.desc())
        .limit(1)
    )
    latest_ic = latest.scalar_one_or_none()
    if latest_ic is None or latest_ic.id != ic.id:
        return ConditionResult(name, False, ("IC_NOT_LATEST_READY",), sha256_hex({}))
    if cycle.repository_id is None:
        return ConditionResult(name, False, ("REPOSITORY_NOT_BOUND",), sha256_hex({}))
    repo = await session.get(Repository, cycle.repository_id)
    if repo is None or repo.canonical_commit != ic.integrated_sha:
        return ConditionResult(
            name,
            False,
            ("CANONICAL_SHA_MISMATCH",),
            sha256_hex(
                {
                    "canonical": repo.canonical_commit if repo else None,
                    "ic": ic.integrated_sha,
                }
            ),
        )
    return ConditionResult(
        name, True, (), sha256_hex({"ic_id": str(ic.id), "sha": ic.integrated_sha})
    )


async def _cond_gates_pass(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ic: IntegrationCandidate | None,
    _release: Release | None,
    _inputs: dict[str, Any],
) -> ConditionResult:
    from core.assurance.guards import required_gates_pass

    name = "required_gates_pass"
    result = await required_gates_pass(session, cycle, None)
    return ConditionResult(name, result.ok, result.reasons, sha256_hex({"reasons": result.reasons}))


async def _cond_approvals(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ic: IntegrationCandidate | None,
    release: Release | None,
    _inputs: dict[str, Any],
) -> ConditionResult:
    from core.planning.guards import architecture_approved, implementation_specs_approved
    from core.product_model.guards import scope_approved

    name = "required_approvals_exist"
    reasons: list[str] = []
    for guard_fn, label in (
        (scope_approved, "SCOPE"),
        (architecture_approved, "ARCHITECTURE"),
        (implementation_specs_approved, "IMPLEMENTATION_SPECS"),
    ):
        gr = await guard_fn(session, cycle, None)
        if not gr.ok:
            reasons.extend(f"{label}:{r}" for r in gr.reasons)
    return ConditionResult(name, not reasons, tuple(reasons), sha256_hex({"reasons": reasons}))


async def _cond_executions_not_stale(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ic: IntegrationCandidate | None,
    _release: Release | None,
    _inputs: dict[str, Any],
) -> ConditionResult:
    name = "required_executions_not_stale"
    reasons: list[str] = []
    stale_tasks = await session.execute(
        select(Task.key).where(
            Task.delivery_cycle_id == cycle.id,
            Task.work_type == WorkType.CODE_CHANGE,
            Task.status.in_([TaskStatus.STALE, TaskStatus.REVALIDATION_REQUIRED]),
        )
    )
    for key in stale_tasks.scalars():
        reasons.append(f"STALE_TASK:{key}")
    if ic is not None:
        ic_commits = await session.execute(
            select(IntegrationCandidateCommit.candidate_commit_id).where(
                IntegrationCandidateCommit.integration_candidate_id == ic.id
            )
        )
        cc_ids = list(ic_commits.scalars())
        if cc_ids:
            ccs = await session.execute(
                select(CandidateCommit).where(CandidateCommit.id.in_(cc_ids))
            )
            exec_ids = [c.execution_id for c in ccs.scalars() if c.execution_id]
            if exec_ids:
                execs = await session.execute(
                    select(Execution.key, Execution.status).where(Execution.id.in_(exec_ids))
                )
                for key, status in execs:
                    if status != ExecutionStatus.COMPLETED:
                        reasons.append(f"EXECUTION_NOT_COMPLETED:{key}:{status.value}")
    return ConditionResult(name, not reasons, tuple(reasons), sha256_hex({"reasons": reasons}))


async def _cond_blocking_findings(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ic: IntegrationCandidate | None,
    _release: Release | None,
    _inputs: dict[str, Any],
) -> ConditionResult:
    name = "blocking_findings"
    q = select(Finding.id).where(
        Finding.delivery_cycle_id == cycle.id,
        Finding.blocking.is_(True),
        Finding.status.in_([FindingStatus.OPEN, FindingStatus.IN_REMEDIATION]),
    )
    if ic is not None:
        q = q.where(
            (Finding.integration_candidate_id == ic.id)
            | (Finding.integration_candidate_id.is_(None))
        )
    count = len((await session.execute(q)).scalars().all())
    ok = count == 0
    return ConditionResult(
        name,
        ok,
        () if ok else (f"BLOCKING_COUNT:{count}",),
        sha256_hex({"count": count}),
    )


async def _cond_mandatory_ac_evidence(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ic: IntegrationCandidate | None,
    _release: Release | None,
    _inputs: dict[str, Any],
) -> ConditionResult:
    name = "mandatory_acceptance_criteria_have_evidence"
    if ic is None or ic.integrated_sha is None:
        return ConditionResult(name, False, ("IC_MISSING",), sha256_hex({}))
    obligations = await session.execute(
        select(VerificationObligation).where(
            VerificationObligation.integration_candidate_id == ic.id,
            VerificationObligation.required.is_(True),
        )
    )
    reasons: list[str] = []
    for obl in obligations.scalars():
        if obl.status == ObligationStatus.WAIVED:
            continue
        cov = await session.execute(
            select(AcceptanceCoverage).where(AcceptanceCoverage.obligation_id == obl.id)
        )
        satisfied = False
        for row in cov.scalars():
            if not row.satisfied:
                continue
            ev = await session.get(Evidence, row.evidence_id)
            if ev is None or ev.commit_sha != ic.integrated_sha:
                continue
            if ev.result.value != "PASS":
                continue
            if not evidence_satisfies_mandatory(
                ev.evidence_type.value,
                list(obl.allowed_evidence_types or []),
                required=True,
            ):
                continue
            satisfied = True
            break
        if not satisfied:
            reasons.append(f"OBLIGATION_UNSATISFIED:{obl.subject_key}")
    return ConditionResult(name, not reasons, tuple(reasons), sha256_hex({"reasons": reasons}))


async def _cond_baselines_pass(
    session: AsyncSession,
    cycle: DeliveryCycle,
    ic: IntegrationCandidate | None,
    _release: Release | None,
    _inputs: dict[str, Any],
) -> ConditionResult:
    name = "required_behavioral_baselines_pass"
    if ic is None or ic.integrated_sha is None:
        return ConditionResult(name, False, ("IC_NOT_READY",), sha256_hex({}))
    obligations = (
        (
            await session.execute(
                select(VerificationObligation).where(
                    VerificationObligation.integration_candidate_id == ic.id,
                    VerificationObligation.gate_type == "BASELINE",
                )
            )
        )
        .scalars()
        .all()
    )
    if not obligations:
        if cycle.type == DeliveryCycleType.GREENFIELD_BUILD:
            return ConditionResult(name, True, (), sha256_hex({"obligations": 0}))
        return ConditionResult(name, True, (), sha256_hex({"obligations": 0}))
    reasons: list[str] = []
    for obl in obligations:
        if obl.status == ObligationStatus.SATISFIED:
            continue
        covered = (
            await session.execute(
                select(AcceptanceCoverage).where(
                    AcceptanceCoverage.obligation_id == obl.id,
                    AcceptanceCoverage.satisfied.is_(True),
                )
            )
        ).scalar_one_or_none()
        if covered is None:
            ev = (
                await session.execute(
                    select(Evidence).where(
                        Evidence.obligation_id == obl.id,
                        Evidence.result == EvidenceResult.PASS,
                        Evidence.commit_sha == ic.integrated_sha,
                    )
                )
            ).scalar_one_or_none()
            if ev is None:
                reasons.append(f"BASELINE_OBLIGATION_OPEN:{obl.subject_key}")
    return ConditionResult(name, not reasons, tuple(reasons), sha256_hex({"reasons": reasons}))


def register_core_eligibility_conditions() -> None:
    reg = get_eligibility_registry()
    reg.register("manifest_valid", _cond_manifest_valid)
    reg.register("integration_candidate_is_current", _cond_ic_current)
    reg.register("required_gates_pass", _cond_gates_pass)
    reg.register("required_approvals_exist", _cond_approvals)
    reg.register("required_executions_not_stale", _cond_executions_not_stale)
    reg.register("blocking_findings", _cond_blocking_findings)
    reg.register("mandatory_acceptance_criteria_have_evidence", _cond_mandatory_ac_evidence)
    reg.register("required_behavioral_baselines_pass", _cond_baselines_pass)


register_core_eligibility_conditions()

import core.release.bugfix_eligibility  # noqa: F401, E402


class ReleaseEligibilityService:
    async def evaluate(
        self,
        session: AsyncSession,
        cycle: DeliveryCycle,
        *,
        release: Release | None = None,
        ic: IntegrationCandidate | None = None,
    ) -> tuple[bool, list[ConditionResult]]:
        if ic is None:
            ic = await self._latest_ready_ic(session, cycle.id)
        required = _default_required_conditions(cycle.type)
        reg = get_eligibility_registry()
        results: list[ConditionResult] = []
        eligible = True
        for cond_name in required:
            fn = reg.get(cond_name)
            if fn is None:
                results.append(
                    ConditionResult(
                        cond_name,
                        False,
                        ("CONDITION_NOT_REGISTERED",),
                        sha256_hex({"missing": cond_name}),
                    )
                )
                eligible = False
                continue
            cr = await fn(session, cycle, ic, release, {})
            results.append(cr)
            if not cr.ok:
                eligible = False
        return eligible, results

    async def recompute_and_persist(
        self,
        session: AsyncSession,
        delivery_cycle_id: uuid.UUID,
        ctx: CommandContext,
        *,
        trigger_event_id: uuid.UUID | None = None,
    ) -> ReleaseEligibilityEvaluation:
        cycle = await session.get(DeliveryCycle, delivery_cycle_id)
        if cycle is None:
            raise ValueError("cycle not found")
        policy_svc = await ensure_policy_version(session)
        if policy_svc.version_row is None:
            raise ValueError("policy version missing")
        policy_version_id = policy_svc.version_row.id
        release = await self._active_release(session, cycle.id)
        ic = await self._latest_ready_ic(session, cycle.id)
        eligible, conditions = await self.evaluate(session, cycle, release=release, ic=ic)
        row = ReleaseEligibilityEvaluation(
            delivery_cycle_id=cycle.id,
            integration_candidate_id=ic.id if ic else None,
            eligible=eligible,
            conditions=[
                {
                    "name": c.name,
                    "ok": c.ok,
                    "reasons": list(c.reasons),
                    "inputs_hash": c.inputs_hash,
                }
                for c in conditions
            ],
            policy_version_id=policy_version_id,
            trigger_event_id=trigger_event_id,
        )
        session.add(row)
        await session.flush()
        if release is not None:
            release.latest_eligibility_id = row.id
            await self._sync_release_status(session, release, eligible, ctx)
        return row

    async def _sync_release_status(
        self,
        session: AsyncSession,
        release: Release,
        eligible: bool,
        ctx: CommandContext,
    ) -> None:
        from core.release.enums import ReleaseStatus
        from core.release.service import ReleaseService

        if release.status in {
            ReleaseStatus.APPROVED,
            ReleaseStatus.EXECUTING,
            ReleaseStatus.RELEASED,
            ReleaseStatus.FAILED,
            ReleaseStatus.SUPERSEDED,
        }:
            return
        if eligible and release.status in {ReleaseStatus.DRAFT, ReleaseStatus.NOT_ELIGIBLE}:
            await ReleaseService().mark_eligible(session, release, ctx)
        elif not eligible and release.status in {ReleaseStatus.DRAFT, ReleaseStatus.ELIGIBLE}:
            await ReleaseService().mark_not_eligible(session, release, ctx)

    async def _latest_ready_ic(
        self, session: AsyncSession, cycle_id: uuid.UUID
    ) -> IntegrationCandidate | None:
        result = await session.execute(
            select(IntegrationCandidate)
            .where(
                IntegrationCandidate.delivery_cycle_id == cycle_id,
                IntegrationCandidate.status == ICStatus.READY,
            )
            .order_by(IntegrationCandidate.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _active_release(self, session: AsyncSession, cycle_id: uuid.UUID) -> Release | None:
        from core.release.enums import ReleaseStatus

        result = await session.execute(
            select(Release)
            .where(
                Release.delivery_cycle_id == cycle_id,
                Release.status.not_in(
                    [ReleaseStatus.SUPERSEDED, ReleaseStatus.FAILED, ReleaseStatus.RELEASED]
                ),
            )
            .order_by(Release.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
