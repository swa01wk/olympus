"""Human promotion decisions for recovered specs, links, architecture, baselines."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.approvals.service import ApprovalService
from core.domain.canonical_json import sha256_hex
from core.domain.enums import (
    ActorKind,
    ActorRole,
    ApprovalStatus,
    ApprovalType,
    KnowledgeClass,
    KnowledgeItemStatus,
    SpecKind,
    SpecStatus,
)
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError, Unauthorized
from core.integration.enums import SpecCodeLinkOrigin, SpecCodeLinkStatus
from core.intelligence.baselines.enums import (
    BaselineStatus,
    PromotionDecisionType,
)
from core.intelligence.baselines.models import BehavioralBaseline, PromotionDecision  # noqa: F401
from core.intelligence.baselines.service import BaselineService
from core.planning.models import Architecture, ImplementationSpec
from core.policy.policy_service import PolicyService, ensure_policy_version
from core.product_model.models import (
    AcceptanceCriterion,
    FeatureSpec,
    KnowledgeItem,
    Requirement,
    UserStory,
)
from core.traceability.models import SpecCodeLink


class PromotionService:
    async def decide(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        subject_type: str,
        subject_id: uuid.UUID,
        decision: str,
        note: str | None,
        ctx: CommandContext,
    ) -> PromotionDecision:
        if ctx.actor.kind != ActorKind.HUMAN:
            raise Unauthorized("Promotion decisions require HUMAN actor")
        try:
            decision_enum = PromotionDecisionType(decision)
        except ValueError as exc:
            raise DomainError(
                code="INVALID_DECISION", message=f"Unknown decision {decision}"
            ) from exc
        existing = (
            await session.execute(
                select(PromotionDecision).where(
                    PromotionDecision.delivery_cycle_id == cycle_id,
                    PromotionDecision.subject_type == subject_type,
                    PromotionDecision.subject_id == subject_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise DomainError(code="ALREADY_DECIDED", message="Subject already decided")
        policy = await ensure_policy_version(session)
        if policy.get("promotion.recovered_spec_requires_human", True) is False:
            raise DomainError(
                code="POLICY_VIOLATION",
                message="Auto-promotion of recovered specs is forbidden",
            )
        result_refs: list[dict[str, Any]] = []
        approval_id: uuid.UUID | None = None
        if subject_type == "FEATURE_SPEC":
            result_refs, approval_id = await self._feature_spec_decision(
                session, cycle_id, subject_id, decision_enum, note, ctx, policy
            )
        elif subject_type == "ARCHITECTURE":
            result_refs, approval_id = await self._architecture_decision(
                session, cycle_id, subject_id, decision_enum, ctx, policy
            )
        elif subject_type == "IMPLEMENTATION_SPEC":
            result_refs, approval_id = await self._implementation_spec_decision(
                session, cycle_id, subject_id, decision_enum, ctx, policy
            )
        elif subject_type == "BASELINE":
            result_refs, approval_id = await self._baseline_decision(
                session, cycle_id, subject_id, decision_enum, ctx
            )
        elif subject_type == "UNCERTAINTY":
            result_refs, approval_id = await self._uncertainty_decision(
                session, cycle_id, subject_id, decision_enum, note, ctx, policy
            )
        else:
            raise DomainError(
                code="INVALID_SUBJECT", message=f"Unknown subject_type {subject_type}"
            )
        row = PromotionDecision(
            delivery_cycle_id=cycle_id,
            subject_type=subject_type,
            subject_id=subject_id,
            decision=decision_enum.value,
            approval_id=approval_id,
            decided_by_actor_id=ctx.actor.id,
            note=note,
            result_refs=result_refs,
        )
        session.add(row)
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="promotion",
            aggregate_id=row.id,
            event_type="promotion.decided",
            payload={
                "subject_type": subject_type,
                "subject_id": str(subject_id),
                "decision": decision_enum.value,
            },
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            delivery_cycle_id=cycle_id,
        )
        return row

    async def _feature_spec_decision(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        spec_id: uuid.UUID,
        decision: PromotionDecisionType,
        note: str | None,
        ctx: CommandContext,
        policy: PolicyService,
    ) -> tuple[list[dict[str, Any]], uuid.UUID | None]:
        spec = await session.get(FeatureSpec, spec_id)
        if spec is None or spec.spec_kind != SpecKind.RECOVERED:
            raise DomainError(code="NOT_FOUND", message="Recovered feature spec not found")
        refs: list[dict[str, Any]] = []
        approval_id: uuid.UUID | None = None
        if decision == PromotionDecisionType.PROMOTE_AS_CANONICAL:
            if ActorRole.APPROVER not in ctx.actor.roles:
                raise Unauthorized("PROMOTE_AS_CANONICAL requires APPROVER")
            approval = await ApprovalService(policy=policy).request(
                session,
                spec.project_id,
                cycle_id,
                ApprovalType.PROMOTION,
                subject_type="FEATURE_SPEC",
                subject_id=spec.id,
                subject_version=spec.version,
                subject_hash=spec.content_hash,
                ctx=ctx,
                policy=policy,
            )
            approval = await ApprovalService(policy=policy).decide(
                session, approval.id, ApprovalStatus.APPROVED, note, ctx
            )
            approval_id = approval.id
            canonical = await self._copy_to_canonical(session, spec, approval.id, ctx)
            spec.status = SpecStatus.PROMOTED
            refs.append({"type": "FEATURE_SPEC", "id": str(canonical.id)})
            await self._confirm_discovered_links(session, spec, canonical, ctx)
            await self._reassign_baselines(session, spec.id, canonical.id)
            await BaselineService().try_auto_activate_for_spec(session, canonical.id, ctx)
            await append_domain_event(
                session,
                aggregate_type="feature_spec",
                aggregate_id=canonical.id,
                event_type="feature_spec.promoted",
                payload={"from": str(spec.id)},
                actor_id=ctx.actor.id,
                correlation_id=ctx.correlation_id,
                project_id=spec.project_id,
                delivery_cycle_id=cycle_id,
            )
        elif decision == PromotionDecisionType.CONFIRM_EXISTING:
            spec.status = SpecStatus.CONFIRMED_EXISTING
        elif decision == PromotionDecisionType.REJECT_AS_NOT_INTENDED:
            spec.status = SpecStatus.REJECTED
            if note:
                session.add(
                    KnowledgeItem(
                        project_id=spec.project_id,
                        delivery_cycle_id=cycle_id,
                        knowledge_class=KnowledgeClass.DECISION,
                        statement=note,
                        subject_refs=[{"feature_spec_id": str(spec.id)}],
                        provenance={"suggested_defect": True},
                        evidence_refs=[],
                        status=KnowledgeItemStatus.ACTIVE,
                    )
                )
        elif decision == PromotionDecisionType.DEFER:
            session.add(
                KnowledgeItem(
                    project_id=spec.project_id,
                    delivery_cycle_id=cycle_id,
                    knowledge_class=KnowledgeClass.UNCERTAINTY,
                    statement=f"Deferred promotion for {spec.lineage_key}",
                    subject_refs=[{"feature_spec_id": str(spec.id)}],
                    provenance={"origin": "PROMOTION_DEFER"},
                    evidence_refs=[],
                    status=KnowledgeItemStatus.ACTIVE,
                )
            )
        else:
            raise DomainError(
                code="INVALID_DECISION", message="Decision not allowed for FEATURE_SPEC"
            )
        await session.flush()
        return refs, approval_id

    async def _copy_to_canonical(
        self,
        session: AsyncSession,
        recovered: FeatureSpec,
        approval_id: uuid.UUID,
        ctx: CommandContext,
    ) -> FeatureSpec:
        body = dict(recovered.body or {})
        canonical = FeatureSpec(
            project_id=recovered.project_id,
            feature_id=recovered.feature_id,
            lineage_key=recovered.lineage_key,
            version=recovered.version + 1,
            status=SpecStatus.APPROVED,
            spec_kind=SpecKind.CANONICAL,
            body=body,
            content_hash=sha256_hex(body),
            promoted_from_id=recovered.id,
            supersedes_id=recovered.id,
            approval_id=approval_id,
        )
        session.add(canonical)
        await session.flush()
        for req in (
            await session.execute(
                select(Requirement).where(Requirement.feature_spec_id == recovered.id)
            )
        ).scalars():
            session.add(
                Requirement(
                    feature_spec_id=canonical.id,
                    lineage_key=req.lineage_key,
                    statement=req.statement,
                    kind=req.kind,
                    priority=req.priority,
                    locked=req.locked,
                )
            )
        for story in (
            await session.execute(
                select(UserStory).where(UserStory.feature_spec_id == recovered.id)
            )
        ).scalars():
            session.add(
                UserStory(
                    feature_spec_id=canonical.id,
                    lineage_key=story.lineage_key,
                    actor=story.actor,
                    goal=story.goal,
                    benefit=story.benefit,
                    locked=story.locked,
                )
            )
        for ac in (
            await session.execute(
                select(AcceptanceCriterion).where(
                    AcceptanceCriterion.feature_spec_id == recovered.id
                )
            )
        ).scalars():
            session.add(
                AcceptanceCriterion(
                    feature_spec_id=canonical.id,
                    lineage_key=ac.lineage_key,
                    statement=ac.statement,
                    given=ac.given,
                    when=ac.when,
                    then=ac.then,
                    mandatory=ac.mandatory,
                    evidence_requirement=ac.evidence_requirement,
                    requirement_keys=list(ac.requirement_keys or []),
                    change_kind="PROMOTED",
                )
            )
        await session.flush()
        return canonical

    async def _reassign_baselines(
        self,
        session: AsyncSession,
        recovered_id: uuid.UUID,
        canonical_id: uuid.UUID,
    ) -> None:
        rows = (
            (
                await session.execute(
                    select(BehavioralBaseline).where(
                        BehavioralBaseline.feature_spec_id == recovered_id
                    )
                )
            )
            .scalars()
            .all()
        )
        for row in rows:
            row.feature_spec_id = canonical_id
        await session.flush()

    async def _confirm_discovered_links(
        self,
        session: AsyncSession,
        recovered: FeatureSpec,
        canonical: FeatureSpec,
        ctx: CommandContext,
    ) -> None:
        links = (
            (
                await session.execute(
                    select(SpecCodeLink).where(
                        SpecCodeLink.spec_id == recovered.id,
                        SpecCodeLink.origin == SpecCodeLinkOrigin.DISCOVERED,
                        SpecCodeLink.status == SpecCodeLinkStatus.ACTIVE,
                    )
                )
            )
            .scalars()
            .all()
        )
        for link in links:
            link.status = SpecCodeLinkStatus.SUPERSEDED
            confirmed = SpecCodeLink(
                project_id=link.project_id,
                repository_id=link.repository_id,
                spec_type="FEATURE_SPEC",
                spec_id=canonical.id,
                spec_lineage_key=canonical.lineage_key,
                code_stable_key=link.code_stable_key,
                relation=link.relation,
                origin=SpecCodeLinkOrigin.HUMAN_CONFIRMED,
                confidence=link.confidence,
                task_id=link.task_id,
                execution_id=link.execution_id,
                commit_sha=link.commit_sha,
                evidence_refs=[
                    *(link.evidence_refs or []),
                    {"type": "DISCOVERED_LINK", "id": str(link.id)},
                ],
                established_index_version_id=link.established_index_version_id,
                last_confirmed_index_version_id=link.last_confirmed_index_version_id,
                status=SpecCodeLinkStatus.ACTIVE,
                promoted_from_link_id=link.id,
            )
            session.add(confirmed)
            await session.flush()
            await append_domain_event(
                session,
                aggregate_type="spec_code_link",
                aggregate_id=confirmed.id,
                event_type="spec_code_link.confirmed",
                payload={"from_link": str(link.id)},
                actor_id=ctx.actor.id,
                correlation_id=ctx.correlation_id,
                project_id=link.project_id,
            )
        await session.flush()

    async def _architecture_decision(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        arch_id: uuid.UUID,
        decision: PromotionDecisionType,
        ctx: CommandContext,
        policy: PolicyService,
    ) -> tuple[list[dict[str, Any]], uuid.UUID | None]:
        arch = await session.get(Architecture, arch_id)
        if arch is None:
            raise DomainError(code="NOT_FOUND", message="Architecture not found")
        if decision != PromotionDecisionType.APPROVE_AS_PROJECT_ARCHITECTURE:
            raise DomainError(code="INVALID_DECISION", message="Invalid architecture decision")
        if ActorRole.APPROVER not in ctx.actor.roles:
            raise Unauthorized("Architecture approval requires APPROVER")
        approval = await ApprovalService(policy=policy).request(
            session,
            arch.project_id,
            cycle_id,
            ApprovalType.ARCHITECTURE,
            subject_type="ARCHITECTURE",
            subject_id=arch.id,
            subject_version=arch.version,
            subject_hash=arch.content_hash,
            ctx=ctx,
            policy=policy,
        )
        approval = await ApprovalService(policy=policy).decide(
            session, approval.id, ApprovalStatus.APPROVED, None, ctx
        )
        arch.status = SpecStatus.APPROVED
        await session.flush()
        return [{"type": "ARCHITECTURE", "id": str(arch.id)}], approval.id

    async def _implementation_spec_decision(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        impl_id: uuid.UUID,
        decision: PromotionDecisionType,
        ctx: CommandContext,
        policy: PolicyService,
    ) -> tuple[list[dict[str, Any]], uuid.UUID | None]:
        impl = await session.get(ImplementationSpec, impl_id)
        if impl is None:
            raise DomainError(code="NOT_FOUND", message="Implementation spec not found")
        if decision != PromotionDecisionType.PROMOTE_AS_CANONICAL:
            raise DomainError(
                code="INVALID_DECISION",
                message="Use PROMOTE_AS_CANONICAL for implementation spec approval",
            )
        if ActorRole.APPROVER not in ctx.actor.roles:
            raise Unauthorized("Implementation spec approval requires APPROVER")
        approval = await ApprovalService(policy=policy).request(
            session,
            impl.project_id,
            cycle_id,
            ApprovalType.IMPLEMENTATION_SPEC,
            subject_type="IMPLEMENTATION_SPEC",
            subject_id=impl.id,
            subject_version=impl.version,
            subject_hash=impl.content_hash,
            ctx=ctx,
            policy=policy,
        )
        approval = await ApprovalService(policy=policy).decide(
            session, approval.id, ApprovalStatus.APPROVED, None, ctx
        )
        impl.status = SpecStatus.APPROVED
        await session.flush()
        return [{"type": "IMPLEMENTATION_SPEC", "id": str(impl.id)}], approval.id

    async def _baseline_decision(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        baseline_id: uuid.UUID,
        decision: PromotionDecisionType,
        ctx: CommandContext,
    ) -> tuple[list[dict[str, Any]], uuid.UUID | None]:
        if decision == PromotionDecisionType.ACTIVATE:
            bl = await BaselineService().activate_human(session, baseline_id, ctx)
            return [{"type": "BASELINE", "id": str(bl.id)}], None
        if decision == PromotionDecisionType.REJECT_AS_NOT_INTENDED:
            rejected = await session.get(BehavioralBaseline, baseline_id)
            if rejected is None:
                raise DomainError(code="NOT_FOUND", message="Baseline not found")
            rejected.status = BaselineStatus.REJECTED
            await session.flush()
            return [{"type": "BASELINE", "id": str(rejected.id)}], None
        raise DomainError(code="INVALID_DECISION", message="Invalid baseline decision")

    async def _uncertainty_decision(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        item_id: uuid.UUID,
        decision: PromotionDecisionType,
        note: str | None,
        ctx: CommandContext,
        policy: PolicyService,
    ) -> tuple[list[dict[str, Any]], uuid.UUID | None]:
        item = await session.get(KnowledgeItem, item_id)
        if item is None or item.knowledge_class != KnowledgeClass.UNCERTAINTY:
            raise DomainError(code="NOT_FOUND", message="Uncertainty not found")
        approval_id: uuid.UUID | None = None
        if decision == PromotionDecisionType.RESOLVE:
            session.add(
                KnowledgeItem(
                    project_id=item.project_id,
                    delivery_cycle_id=cycle_id,
                    knowledge_class=KnowledgeClass.DECISION,
                    statement=note or "Resolved uncertainty",
                    subject_refs=item.subject_refs,
                    provenance={"resolves": str(item.id)},
                    evidence_refs=item.evidence_refs,
                    status=KnowledgeItemStatus.ACTIVE,
                )
            )
            item.status = KnowledgeItemStatus.SUPERSEDED
        elif decision == PromotionDecisionType.ACCEPT_KNOWN_GAP:
            if ActorRole.APPROVER not in ctx.actor.roles:
                raise Unauthorized("ACCEPT_KNOWN_GAP requires APPROVER")
            approval = await ApprovalService(policy=policy).request(
                session,
                item.project_id,
                cycle_id,
                ApprovalType.PROMOTION,
                subject_type="UNCERTAINTY",
                subject_id=item.id,
                subject_version=1,
                subject_hash=sha256_hex({"statement": item.statement}),
                ctx=ctx,
                policy=policy,
            )
            approval = await ApprovalService(policy=policy).decide(
                session, approval.id, ApprovalStatus.APPROVED, note, ctx
            )
            approval_id = approval.id
            prov = dict(item.provenance or {})
            prov["accepted_known_gap"] = True
            item.provenance = prov
        else:
            raise DomainError(code="INVALID_DECISION", message="Invalid uncertainty decision")
        await session.flush()
        return [{"type": "KNOWLEDGE_ITEM", "id": str(item.id)}], approval_id
