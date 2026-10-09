"""Defect intake and lifecycle."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.approvals.models import Approval
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import ApprovalStatus, DeliveryCycleType, SpecStatus
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.domain.repositories.models import Repository
from core.domain.sequences import next_project_key
from core.integrations.inbound.storage import sha256_text
from core.intelligence.code_index.retrieval.hybrid import HybridRetrieval
from core.product_model.changes.guards import project_change_ready
from core.product_model.defects.models import (
    Defect,
    ExpectedBehaviorResolution,
    RootCauseAnalysis,
)
from core.product_model.defects.schemas import (
    DefectTriage,
    ExpectedBehaviorProposal,
    RootCauseHypothesis,
)
from core.product_model.defects.triage import (
    DefectTriageValidator,
    normalize_defect_triage_signature,
)
from core.product_model.models import AcceptanceCriterion, Feature, FeatureSpec
from core.product_model.sources.service import ProductSourceService

_MAX_AC_CITATIONS = 80


class DefectService:
    async def intake(
        self,
        session: AsyncSession,
        *,
        project_id: uuid.UUID,
        title: str,
        description: str,
        source_type: str,
        external_ref: str | None,
        inbound_event_id: uuid.UUID | None,
        ctx: CommandContext,
    ) -> Defect:
        if external_ref:
            existing = (
                await session.execute(
                    select(Defect).where(
                        Defect.project_id == project_id,
                        Defect.source_type == source_type,
                        Defect.external_ref == external_ref,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                return existing

        repo = (
            await session.execute(select(Repository).where(Repository.project_id == project_id))
        ).scalar_one_or_none()
        if repo is None or repo.canonical_commit is None:
            raise DomainError(code="INVALID_STATE", message="Repository not ready")

        from types import SimpleNamespace

        guard = await project_change_ready(
            session,
            SimpleNamespace(project_id=project_id, type=DeliveryCycleType.BUG_FIX),  # type: ignore[arg-type]
            ctx,
        )
        if not guard.ok:
            raise DomainError(
                code="PROJECT_NOT_READY",
                message="Project not ready for defect intake",
                details={"reasons": list(guard.reasons)},
            )

        text_hash = sha256_text(description)
        lineage_key = f"defect-{external_ref or text_hash[:16]}"
        source_result = await ProductSourceService().ingest(
            session,
            project_id=project_id,
            lineage_key=lineage_key,
            source_type="DEFECT_REPORT",
            title=title,
            mime_type="text/markdown",
            content_hash=text_hash,
            raw_storage_ref=f"inline://{lineage_key}",
            text=description,
            ctx=ctx,
            inbound_event_id=inbound_event_id,
        )
        product_source_id = uuid.UUID(source_result["product_source_id"])

        cycle = await DeliveryCycleService().create(
            session,
            project_id,
            DeliveryCycleType.BUG_FIX,
            title,
            ctx,
        )
        key = await next_project_key(session, project_id, "defect", prefix="DEF")
        defect = Defect(
            key=key,
            project_id=project_id,
            delivery_cycle_id=cycle.id,
            title=title,
            description=description,
            product_source_id=product_source_id,
            source_type=source_type,
            external_ref=external_ref,
            inbound_event_id=inbound_event_id,
            affected_sha=repo.canonical_commit,
            status="REPORTED",
        )
        session.add(defect)
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="defect",
            aggregate_id=defect.id,
            event_type="defect.reported",
            payload={"key": key, "cycle_id": str(cycle.id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=project_id,
            delivery_cycle_id=cycle.id,
        )
        from core.product_model.defects.orchestrator import BugFixOrchestrator

        await BugFixOrchestrator().schedule_defect_triage(session, cycle.id, ctx)
        return defect

    async def get(self, session: AsyncSession, defect_id: uuid.UUID) -> Defect:
        row = await session.get(Defect, defect_id)
        if row is None:
            raise DomainError(code="NOT_FOUND", message="Defect not found")
        return row

    async def get_by_cycle(self, session: AsyncSession, cycle_id: uuid.UUID) -> Defect | None:
        return (
            await session.execute(select(Defect).where(Defect.delivery_cycle_id == cycle_id))
        ).scalar_one_or_none()

    async def build_triage_context(
        self, session: AsyncSession, cycle_id: uuid.UUID
    ) -> dict[str, Any]:
        defect = await self.get_by_cycle(session, cycle_id)
        if defect is None:
            raise DomainError(code="NOT_FOUND", message="Defect not linked")
        hybrid = HybridRetrieval(session)
        candidates = await hybrid.resolve_feature(defect.description, defect.project_id)
        return {
            "defect_title": defect.title,
            "defect_description": defect.description,
            "candidate_features_json": [c.model_dump(mode="json") for c in candidates],
            "affected_sha": defect.affected_sha,
        }

    async def persist_triage(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        triage: DefectTriage,
        execution_id: uuid.UUID,
        ctx: CommandContext,
    ) -> Defect:
        defect = await self.get_by_cycle(session, cycle_id)
        if defect is None:
            raise DomainError(code="NOT_FOUND", message="Defect not linked")
        triage = normalize_defect_triage_signature(triage, defect.description)
        hybrid = HybridRetrieval(session)
        candidates = await hybrid.resolve_feature(defect.description, defect.project_id)
        candidate_keys = {c.feature_key for c in candidates if c.feature_key}
        ok, errors = await DefectTriageValidator().validate(
            session, defect.project_id, triage, candidate_keys
        )
        if not ok:
            raise DomainError(
                code="INVALID_INPUT",
                message="Invalid triage",
                details={"errors": errors},
            )

        linked: list[str] = []
        for fkey in triage.feature_keys:
            feat = (
                await session.execute(
                    select(Feature).where(
                        Feature.project_id == defect.project_id, Feature.key == fkey
                    )
                )
            ).scalar_one_or_none()
            if feat is not None:
                linked.append(str(feat.id))

        defect.triage = triage.model_dump(mode="json")
        defect.severity = triage.severity
        defect.linked_feature_ids = linked
        defect.status = "TRIAGED"
        defect.affected_sha = defect.affected_sha
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="defect",
            aggregate_id=defect.id,
            event_type="defect.triaged",
            payload={"execution_id": str(execution_id), "severity": triage.severity},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=defect.project_id,
            delivery_cycle_id=cycle_id,
        )
        return defect

    async def approved_ac_citations(
        self, session: AsyncSession, defect: Defect
    ) -> list[dict[str, Any]]:
        """Approved ACs of the project, triaged features first, cited as ``SPEC/AC``.

        Recovered AC lineage keys (``AC-1``) repeat across specs, so citations carry the spec key.
        """
        triage = defect.triage or {}
        focus = {
            str(k)
            for k in [
                *(triage.get("feature_keys") or []),
                *(triage.get("suspected_ac_lineage_keys") or []),
            ]
        }
        rows = (
            await session.execute(
                select(Feature.key, FeatureSpec.lineage_key, AcceptanceCriterion)
                .join(FeatureSpec, AcceptanceCriterion.feature_spec_id == FeatureSpec.id)
                .join(Feature, Feature.id == FeatureSpec.feature_id)
                .where(
                    FeatureSpec.project_id == defect.project_id,
                    FeatureSpec.status == SpecStatus.APPROVED,
                )
                .order_by(FeatureSpec.lineage_key, AcceptanceCriterion.lineage_key)
            )
        ).all()
        ranked = sorted(rows, key=lambda r: not ({r[0], r[1], r[2].lineage_key} & focus))
        return [
            {
                "citation": f"{spec_key}/{ac.lineage_key}",
                "feature_key": feature_key,
                "statement": ac.statement,
                "given": ac.given,
                "when": ac.when,
                "then": ac.then,
            }
            for feature_key, spec_key, ac in ranked[:_MAX_AC_CITATIONS]
        ]

    async def _resolve_ac_citation(
        self, session: AsyncSession, project_id: uuid.UUID, citation: str
    ) -> AcceptanceCriterion:
        spec_key, _, ac_key = citation.rpartition("/")
        stmt = (
            select(AcceptanceCriterion)
            .join(FeatureSpec, AcceptanceCriterion.feature_spec_id == FeatureSpec.id)
            .where(
                FeatureSpec.project_id == project_id,
                FeatureSpec.status == SpecStatus.APPROVED,
                AcceptanceCriterion.lineage_key == ac_key,
            )
        )
        if spec_key:
            stmt = stmt.where(FeatureSpec.lineage_key == spec_key)
        matches = (await session.execute(stmt)).scalars().all()
        if not matches:
            raise DomainError(code="INVALID_INPUT", message=f"AC not approved: {citation}")
        if len(matches) > 1:
            raise DomainError(
                code="INVALID_INPUT", message=f"AC citation ambiguous, cite SPEC/AC: {citation}"
            )
        return matches[0]

    async def persist_expected_behavior(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        proposal: ExpectedBehaviorProposal,
        execution_id: uuid.UUID,
        ctx: CommandContext,
    ) -> ExpectedBehaviorResolution:
        defect = await self.get_by_cycle(session, cycle_id)
        if defect is None:
            raise DomainError(code="NOT_FOUND", message="Defect not linked")

        ac_ids: list[str] = []
        resolution_kind = "SPECIFIED"
        if proposal.classification == "SPECIFIED":
            for citation in proposal.cited_ac_lineage_keys:
                ac = await self._resolve_ac_citation(session, defect.project_id, citation)
                ac_ids.append(str(ac.id))
        elif proposal.classification == "NOT_A_DEFECT":
            resolution_kind = "NOT_A_DEFECT"
            defect.status = "REJECTED"
        else:
            resolution_kind = proposal.classification

        row = ExpectedBehaviorResolution(
            defect_id=defect.id,
            classification=proposal.classification,
            resolution_kind=resolution_kind,
            ac_ids=ac_ids,
            statement=proposal.expected_behavior_statement,
            execution_id=execution_id,
        )
        session.add(row)
        defect.expected_ac_ids = ac_ids
        if proposal.classification != "NOT_A_DEFECT":
            defect.status = "EXPECTED_RESOLVED"
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="defect",
            aggregate_id=defect.id,
            event_type="defect.expected_behavior_resolved",
            payload={"classification": proposal.classification},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=defect.project_id,
            delivery_cycle_id=cycle_id,
        )
        return row

    async def persist_root_cause(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        hypothesis: RootCauseHypothesis,
        trace_correlation_id: uuid.UUID,
        execution_id: uuid.UUID,
        ctx: CommandContext,
        *,
        candidate_keys: set[str],
    ) -> RootCauseAnalysis:
        defect = await self.get_by_cycle(session, cycle_id)
        if defect is None:
            raise DomainError(code="NOT_FOUND", message="Defect not linked")
        for key in hypothesis.faulty_stable_keys:
            if key not in candidate_keys:
                raise DomainError(
                    code="INVALID_INPUT",
                    message=f"faulty key not in candidates: {key}",
                )
        row = RootCauseAnalysis(
            defect_id=defect.id,
            trace_correlation_id=trace_correlation_id,
            execution_id=execution_id,
            faulty_stable_keys=hypothesis.faulty_stable_keys,
            explanation=hypothesis.explanation,
            knowledge_class="INFERENCE",
            confidence=hypothesis.confidence,
            fix_outline=hypothesis.fix_outline,
            regression_risks=hypothesis.regression_risks,
            cited_evidence_ids=hypothesis.cited_evidence_ids,
            status="PROPOSED",
        )
        session.add(row)
        defect.status = "ROOT_CAUSED"
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="defect",
            aggregate_id=defect.id,
            event_type="defect.root_caused",
            payload={"rca_id": str(row.id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=defect.project_id,
            delivery_cycle_id=cycle_id,
        )
        return row

    async def create_from_suggestion(
        self,
        session: AsyncSession,
        knowledge_item_id: uuid.UUID,
        ctx: CommandContext,
    ) -> Defect:
        from core.product_model.models import KnowledgeItem

        item = await session.get(KnowledgeItem, knowledge_item_id)
        if item is None:
            raise DomainError(code="NOT_FOUND", message="KnowledgeItem not found")
        prov = item.provenance or {}
        if not prov.get("suggested_defect"):
            raise DomainError(code="INVALID_INPUT", message="Not a defect suggestion")
        return await self.intake(
            session,
            project_id=item.project_id,
            title=str(prov.get("title") or item.statement or "Suggested defect"),
            description=str(item.statement or ""),
            source_type="knowledge_suggestion",
            external_ref=str(item.id),
            inbound_event_id=None,
            ctx=ctx,
        )

    async def list_reproductions(self, session: AsyncSession, defect_id: uuid.UUID) -> list[Any]:
        from core.product_model.defects.models import Reproduction

        return list(
            (
                await session.execute(
                    select(Reproduction)
                    .where(Reproduction.defect_id == defect_id)
                    .order_by(Reproduction.created_at.asc())
                )
            ).scalars()
        )

    async def latest_trace_correlation(
        self, session: AsyncSession, defect_id: uuid.UUID
    ) -> Any | None:
        from core.product_model.defects.models import Reproduction, TraceCorrelation

        return (
            await session.execute(
                select(TraceCorrelation)
                .join(Reproduction, TraceCorrelation.reproduction_id == Reproduction.id)
                .where(Reproduction.defect_id == defect_id)
                .order_by(TraceCorrelation.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def latest_root_cause(
        self, session: AsyncSession, defect_id: uuid.UUID
    ) -> RootCauseAnalysis | None:
        return (
            await session.execute(
                select(RootCauseAnalysis)
                .where(RootCauseAnalysis.defect_id == defect_id)
                .order_by(RootCauseAnalysis.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def proceed_unreproduced(
        self,
        session: AsyncSession,
        defect_id: uuid.UUID,
        ctx: CommandContext,
        *,
        reason: str,
    ) -> Approval:
        from core.domain.approvals.service import ApprovalService
        from core.domain.enums import ActorKind, ActorRole, ApprovalType
        from core.domain.exceptions import Unauthorized
        from core.policy.policy_service import ensure_policy_version

        if ctx.actor.kind != ActorKind.HUMAN or ActorRole.APPROVER not in ctx.actor.roles:
            raise Unauthorized("HUMAN approver required for proceed_unreproduced")
        policy = await ensure_policy_version(session)
        if not policy.get("bugfix.allow_unreproduced", False):
            raise DomainError(
                code="POLICY_FORBIDS",
                message="bugfix.allow_unreproduced is false",
            )
        defect = await self.get(session, defect_id)
        if defect.status != "NOT_REPRODUCIBLE":
            raise DomainError(
                code="INVALID_STATE",
                message=f"Defect must be NOT_REPRODUCIBLE, got {defect.status}",
            )
        if defect.delivery_cycle_id is None:
            raise DomainError(code="INVALID_STATE", message="Defect has no cycle")
        subject_hash = sha256_text(f"{defect.id}:{reason}")
        approval = await ApprovalService(policy=policy).request(
            session,
            defect.project_id,
            defect.delivery_cycle_id,
            ApprovalType.UNREPRODUCED_REPAIR,
            "DEFECT",
            defect.id,
            1,
            subject_hash,
            ctx,
            policy=policy,
        )
        return await ApprovalService(policy=policy).decide(
            session,
            approval.id,
            ApprovalStatus.APPROVED,
            reason,
            ctx,
        )

    async def reject_defect(
        self,
        session: AsyncSession,
        defect_id: uuid.UUID,
        ctx: CommandContext,
        *,
        reason: str | None = None,
    ) -> Defect:
        from core.domain.enums import ActorKind, ActorRole
        from core.domain.exceptions import Unauthorized

        if ctx.actor.kind != ActorKind.HUMAN or ActorRole.OPERATOR not in ctx.actor.roles:
            raise Unauthorized("HUMAN operator required to reject defect")
        defect = await self.get(session, defect_id)
        defect.status = "REJECTED"
        if defect.delivery_cycle_id is not None:
            from core.domain.delivery_cycles.models import DeliveryCycle

            cycle = await session.get(DeliveryCycle, defect.delivery_cycle_id)
            if cycle is not None and cycle.state not in ("CANCELLED", "COMPLETE", "FAILED"):
                svc = DeliveryCycleService()
                allowed = await svc.allowed_commands(session, cycle, ctx)
                cancel = next((c for c in allowed if c.get("command") == "cancel"), None)
                if cancel and cancel.get("allowed"):
                    await svc.run_command(session, cycle.id, "cancel", cycle.state, ctx)
        await append_domain_event(
            session,
            aggregate_type="defect",
            aggregate_id=defect.id,
            event_type="defect.rejected",
            payload={"reason": reason or ""},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=defect.project_id,
            delivery_cycle_id=defect.delivery_cycle_id,
        )
        await session.flush()
        return defect
