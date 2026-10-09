"""Deterministic gate finalization (Phase 09 §6)."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.enums import (
    EvidenceResult,
    EvidenceType,
    GateStatus,
    GateType,
    ObligationStatus,
)
from core.assurance.evidence_rules import evidence_satisfies_mandatory
from core.assurance.models import (
    AcceptanceCoverage,
    Evidence,
    Finding,
    Gate,
    VerificationObligation,
)
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError, Unauthorized
from core.domain.repositories.models import Repository
from core.domain.sequences import next_project_key
from core.integration.enums import FindingStatus
from core.integration.models import IntegrationCandidate
from core.policy.policy_service import ensure_policy_version, get_cached_policy_content

FINALIZER_ACTOR = "SYSTEM:gate_finalizer"


@dataclass(frozen=True)
class GateDecisionInputs:
    integrated_sha: str
    canonical_commit: str | None
    gate_type: str
    obligations: tuple[dict[str, Any], ...]
    coverage_rows: tuple[dict[str, Any], ...]
    evidence_rows: tuple[dict[str, Any], ...]
    blocking_findings: tuple[str, ...]
    agent_recommendation: dict[str, Any] | None
    policy: dict[str, Any]


@dataclass
class GateDecision:
    status: GateStatus
    reasons: list[str] = field(default_factory=list)
    recommendation_overridden: bool = False
    inputs_hash: str = ""


def _hash_inputs(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def decide(inputs: GateDecisionInputs) -> GateDecision:
    reasons: list[str] = []
    if inputs.canonical_commit != inputs.integrated_sha:
        reasons.append("CANONICAL_REVISION_MISMATCH")

    bad_sha = [
        e["key"]
        for e in inputs.evidence_rows
        if e.get("commit_sha") != inputs.integrated_sha and not e.get("at_affected_sha")
    ]
    if bad_sha:
        reasons.append(f"EVIDENCE_SHA_MISMATCH:{','.join(bad_sha[:5])}")

    if inputs.gate_type == GateType.INTEGRATION.value:
        has_integration = any(
            e.get("evidence_type") == EvidenceType.INTEGRATION_CHECK.value
            and e.get("result") == EvidenceResult.PASS.value
            for e in inputs.evidence_rows
        )
        if not has_integration:
            reasons.append("INTEGRATION_EVIDENCE_MISSING")

    if inputs.gate_type in (GateType.SENTINEL.value, GateType.BASELINE.value):
        for obl in inputs.obligations:
            if not obl.get("required"):
                continue
            if obl.get("status") == ObligationStatus.WAIVED.value:
                continue
            obl_id = obl["id"]
            satisfied = False
            for cov in inputs.coverage_rows:
                if cov.get("obligation_id") != obl_id or not cov.get("satisfied"):
                    continue
                ev = next(
                    (e for e in inputs.evidence_rows if e.get("id") == cov.get("evidence_id")),
                    None,
                )
                if ev is None:
                    continue
                if ev.get("result") != EvidenceResult.PASS.value:
                    continue
                if not evidence_satisfies_mandatory(
                    str(ev.get("evidence_type")),
                    list(obl.get("allowed_evidence_types") or []),
                    required=True,
                ):
                    continue
                satisfied = True
                break
            if not satisfied:
                reasons.append(f"OBLIGATION_UNSATISFIED:{obl.get('subject_key', obl_id)}")

    if inputs.blocking_findings:
        reasons.append(f"BLOCKING_FINDINGS:{len(inputs.blocking_findings)}")

    assurance_policy = inputs.policy.get("assurance", {})
    if inputs.gate_type == GateType.WARDEN.value and assurance_policy.get(
        "warden_review_required", True
    ):
        has_review = any(
            e.get("evidence_type") == "STATIC_REVIEW"
            and e.get("result") == EvidenceResult.PASS.value
            for e in inputs.evidence_rows
        )
        if not has_review:
            reasons.append("WARDEN_REVIEW_EVIDENCE_MISSING")

    recommendation_overridden = False
    rec = inputs.agent_recommendation or {}
    if rec.get("recommended") == "FAIL" and not reasons:
        recommendation_overridden = True

    if reasons:
        return GateDecision(
            status=GateStatus.FAIL,
            reasons=reasons,
            recommendation_overridden=recommendation_overridden,
            inputs_hash=_hash_inputs(
                {
                    "integrated_sha": inputs.integrated_sha,
                    "reasons": reasons,
                    "gate_type": inputs.gate_type,
                }
            ),
        )
    return GateDecision(
        status=GateStatus.PASS,
        reasons=["ALL_CHECKS_PASSED"],
        recommendation_overridden=recommendation_overridden,
        inputs_hash=_hash_inputs(
            {
                "integrated_sha": inputs.integrated_sha,
                "gate_type": inputs.gate_type,
                "status": "PASS",
            }
        ),
    )


class GateFinalizerService:
    async def finalize(
        self,
        session: AsyncSession,
        gate_id: uuid.UUID,
        ctx: CommandContext,
    ) -> Gate:
        if ctx.actor.kind.name == "AGENT":
            raise Unauthorized("Agents cannot finalize gates")
        gate = await session.get(Gate, gate_id)
        if gate is None:
            raise DomainError(code="NOT_FOUND", message="Gate not found")
        if gate.status in {GateStatus.PASS, GateStatus.FAIL}:
            raise DomainError(code="INVALID_STATE", message="Gate already finalized")
        ic = await session.get(IntegrationCandidate, gate.integration_candidate_id)
        if ic is None or ic.integrated_sha is None:
            raise DomainError(code="IC_NOT_READY", message="Integration candidate not READY")
        repo = await session.get(Repository, ic.repository_id)
        decision = await self._compute_decision(session, gate, ic, repo)
        if gate.gate_type == GateType.BASELINE:
            await self._provisional_baseline_findings(session, gate, ic, ctx)
        policy_svc = await ensure_policy_version(session)
        gate.status = decision.status
        gate.reasons = decision.reasons
        gate.inputs_hash = decision.inputs_hash
        gate.finalized_at = datetime.now(UTC)
        gate.finalized_by = FINALIZER_ACTOR
        gate.policy_version_id = (
            policy_svc.version_row.id if policy_svc.version_row is not None else None
        )
        if decision.recommendation_overridden:
            gate.reasons = list(gate.reasons) + ["recommendation_overridden"]
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="gate",
            aggregate_id=gate.id,
            event_type="gate.finalized",
            payload={
                "gate_type": gate.gate_type.value,
                "status": gate.status.value,
                "reasons": gate.reasons,
            },
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=(repo.project_id if repo else None),
            delivery_cycle_id=gate.delivery_cycle_id,
        )
        await self._maybe_finalize_siblings(session, ic.id, ctx)
        return gate

    async def _compute_decision(
        self,
        session: AsyncSession,
        gate: Gate,
        ic: IntegrationCandidate,
        repo: Repository | None,
    ) -> GateDecision:
        obligations = await session.execute(
            select(VerificationObligation).where(
                VerificationObligation.integration_candidate_id == ic.id,
                VerificationObligation.gate_type == gate.gate_type.value,
            )
        )
        obl_rows = [
            {
                "id": str(o.id),
                "required": o.required,
                "status": o.status.value,
                "subject_key": o.subject_key,
                "allowed_evidence_types": o.allowed_evidence_types,
            }
            for o in obligations.scalars()
        ]
        evidence = await session.execute(
            select(Evidence).where(
                Evidence.integration_candidate_id == ic.id,
            )
        )
        ev_rows = [
            {
                "id": str(e.id),
                "key": e.key,
                "commit_sha": e.commit_sha,
                "evidence_type": e.evidence_type.value,
                "result": e.result.value,
                "at_affected_sha": (e.details or {}).get("phase") == "REGRESSION_VALIDATION",
            }
            for e in evidence.scalars()
        ]
        obl_ids = [uuid.UUID(str(o["id"])) for o in obl_rows]
        if obl_ids:
            coverage = await session.execute(
                select(AcceptanceCoverage).where(AcceptanceCoverage.obligation_id.in_(obl_ids))
            )
        else:
            coverage = await session.execute(
                select(AcceptanceCoverage).where(AcceptanceCoverage.id.is_(None))
            )
        cov_rows = [
            {
                "obligation_id": str(c.obligation_id),
                "evidence_id": str(c.evidence_id),
                "satisfied": c.satisfied,
            }
            for c in coverage.scalars()
        ]
        findings = await session.execute(
            select(Finding).where(
                Finding.integration_candidate_id == ic.id,
                Finding.blocking.is_(True),
                Finding.status.in_([FindingStatus.OPEN, FindingStatus.IN_REMEDIATION]),
            )
        )
        blocking = tuple(f.key for f in findings.scalars())
        policy = get_cached_policy_content()
        assert ic.integrated_sha is not None
        inputs = GateDecisionInputs(
            integrated_sha=ic.integrated_sha,
            canonical_commit=repo.canonical_commit if repo else None,
            gate_type=gate.gate_type.value,
            obligations=tuple(obl_rows),
            coverage_rows=tuple(cov_rows),
            evidence_rows=tuple(ev_rows),
            blocking_findings=blocking,
            agent_recommendation=gate.recommendation,
            policy=policy,
        )
        return decide(inputs)

    async def _provisional_baseline_findings(
        self,
        session: AsyncSession,
        gate: Gate,
        ic: IntegrationCandidate,
        ctx: CommandContext,
    ) -> None:
        from core.assurance.findings import FindingService
        from core.integration.enums import FindingSeverity, FindingSource
        from core.intelligence.baselines.models import BehavioralBaseline
        from core.intelligence.baselines.provisional import known_gaps_for_baseline

        obligations = (
            await session.execute(
                select(VerificationObligation).where(
                    VerificationObligation.integration_candidate_id == ic.id,
                    VerificationObligation.gate_type == GateType.BASELINE.value,
                    VerificationObligation.subject_type == "BASELINE",
                )
            )
        ).scalars()
        assert ic.integrated_sha is not None
        cycle = await session.get(DeliveryCycle, ic.delivery_cycle_id)
        project_id = cycle.project_id if cycle else None
        if project_id is None:
            return
        for obl in obligations:
            bl = await session.get(BehavioralBaseline, obl.subject_id)
            if bl is None or not bl.provisional:
                continue
            ev = (
                await session.execute(
                    select(Evidence)
                    .where(
                        Evidence.obligation_id == obl.id,
                        Evidence.result == EvidenceResult.FAIL,
                        Evidence.commit_sha == ic.integrated_sha,
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if ev is None:
                continue
            known_gaps = await known_gaps_for_baseline(session, bl)
            await FindingService().create(
                session,
                project_id=project_id,
                delivery_cycle_id=ic.delivery_cycle_id,
                source=FindingSource.SENTINEL,
                category="RISK",
                severity=FindingSeverity.MINOR,
                title=f"Provisional baseline contradicted: {bl.lineage_key}",
                detail={
                    "baseline_id": str(bl.id),
                    "obligation_id": str(obl.id),
                    "evidence_id": str(ev.id),
                    "known_gap": True,
                    "known_gaps": known_gaps,
                },
                ctx=ctx,
                integration_candidate_id=ic.id,
                commit_sha=ic.integrated_sha,
            )

    async def _maybe_finalize_siblings(
        self,
        session: AsyncSession,
        ic_id: uuid.UUID,
        ctx: CommandContext,
    ) -> None:
        gates = await session.execute(select(Gate).where(Gate.integration_candidate_id == ic_id))
        pending = [g for g in gates.scalars() if g.status == GateStatus.PENDING]
        if not pending:
            return
        all_final = all(g.status in {GateStatus.PASS, GateStatus.FAIL} for g in gates.scalars())
        if all_final:
            from core.assurance.release_hook import recompute_release_eligibility

            ic = await session.get(IntegrationCandidate, ic_id)
            if ic is not None:
                await recompute_release_eligibility(session, ic.delivery_cycle_id)


def _policy_gate_types(cycle_type_value: str) -> list[GateType]:
    policy = get_cached_policy_content().get("assurance", {})
    required = policy.get("required_gates", {})
    names: list[str] = list(
        required.get(
            cycle_type_value,
            required.get(
                "default",
                [
                    GateType.INTEGRATION.value,
                    GateType.WARDEN.value,
                    GateType.SENTINEL.value,
                ],
            ),
        )
    )
    if not names:
        names = [
            GateType.INTEGRATION.value,
            GateType.WARDEN.value,
            GateType.SENTINEL.value,
        ]
    out: list[GateType] = []
    for name in names:
        try:
            out.append(GateType(name))
        except ValueError:
            continue
    return out


class GateService:
    async def create_pending_gates(
        self,
        session: AsyncSession,
        *,
        project_id: uuid.UUID,
        delivery_cycle_id: uuid.UUID,
        integration_candidate_id: uuid.UUID,
        cycle_type_value: str,
        ctx: CommandContext,
    ) -> list[Gate]:
        created: list[Gate] = []
        for gate_type in _policy_gate_types(cycle_type_value):
            key = await next_project_key(session, project_id, "gate", prefix="GT")
            row = Gate(
                key=key,
                delivery_cycle_id=delivery_cycle_id,
                integration_candidate_id=integration_candidate_id,
                gate_type=gate_type,
                status=GateStatus.PENDING,
                reasons=[],
            )
            session.add(row)
            created.append(row)
        await session.flush()
        return created
