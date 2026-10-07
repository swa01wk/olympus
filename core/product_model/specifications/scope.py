from __future__ import annotations

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.approvals.service import ApprovalService
from core.domain.canonical_json import sha256_hex
from core.domain.enums import (
    ActorKind,
    ActorRole,
    ApprovalType,
    EntityStatus,
    SpecStatus,
)
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError, Unauthorized
from core.policy.policy_service import ensure_policy_version
from core.product_model.models import (
    AcceptanceCriterion,
    Capability,
    Feature,
    FeatureSpec,
    Requirement,
    ScopeSet,
    ScopeSetItem,
    UserStory,
)


class ScopeService:
    def __init__(self) -> None:
        self._approvals = ApprovalService()

    async def request_scope_approval(
        self,
        session: AsyncSession,
        delivery_cycle_id: uuid.UUID,
        feature_spec_ids: list[uuid.UUID],
        project_id: uuid.UUID,
        ctx: CommandContext,
    ) -> tuple[ScopeSet, uuid.UUID]:
        if ctx.actor.kind == ActorKind.AGENT:
            raise Unauthorized("AGENT cannot request scope approval")

        specs: list[FeatureSpec] = []
        for spec_id in feature_spec_ids:
            spec = await session.get(FeatureSpec, spec_id)
            if spec is None:
                raise DomainError(code="NOT_FOUND", message=f"FeatureSpec {spec_id} not found")
            if spec.status not in {SpecStatus.PROPOSED, SpecStatus.DRAFT}:
                raise DomainError(
                    code="INVALID_STATE",
                    message=f"FeatureSpec {spec_id} must be PROPOSED or DRAFT",
                )
            specs.append(spec)

        spec_fingerprints = sorted(
            [{"id": str(s.id), "version": s.version, "hash": s.content_hash} for s in specs],
            key=lambda item: str(item["id"]),
        )
        payload = json.dumps(spec_fingerprints, sort_keys=True, separators=(",", ":"))
        content_hash = sha256_hex(payload)
        scope_set = ScopeSet(
            delivery_cycle_id=delivery_cycle_id,
            content_hash=content_hash,
            created_by_actor_id=ctx.actor.id,
        )
        session.add(scope_set)
        await session.flush()
        for spec in specs:
            session.add(ScopeSetItem(scope_set_id=scope_set.id, feature_spec_id=spec.id))

        policy = await ensure_policy_version(session)
        approval = await self._approvals.request(
            session,
            project_id,
            delivery_cycle_id,
            ApprovalType.SCOPE,
            subject_type="scope_set",
            subject_id=scope_set.id,
            subject_version=1,
            subject_hash=content_hash,
            ctx=ctx,
            policy=policy,
        )
        await append_domain_event(
            session,
            aggregate_type="scope",
            aggregate_id=scope_set.id,
            event_type="scope.approval_requested",
            payload={"approval_id": str(approval.id), "spec_count": len(specs)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
        )
        return scope_set, approval.id

    async def on_scope_approved(
        self,
        session: AsyncSession,
        scope_set_id: uuid.UUID,
        approval_id: uuid.UUID,
        ctx: CommandContext,
    ) -> None:
        scope_set = await session.get(ScopeSet, scope_set_id)
        if scope_set is None:
            return
        items = await session.execute(
            select(ScopeSetItem).where(ScopeSetItem.scope_set_id == scope_set_id)
        )
        for item in items.scalars():
            spec = await session.get(FeatureSpec, item.feature_spec_id)
            if spec is None or spec.status == SpecStatus.APPROVED:
                continue
            spec.status = SpecStatus.APPROVED
            spec.approval_id = approval_id
            feature = await session.get(Feature, spec.feature_id)
            if feature and feature.status != EntityStatus.APPROVED:
                feature.status = EntityStatus.APPROVED
                if feature.capability_id:
                    cap = await session.get(Capability, feature.capability_id)
                    if cap and cap.status != EntityStatus.APPROVED:
                        cap.status = EntityStatus.APPROVED
            req_rows = await session.execute(
                select(Requirement).where(Requirement.feature_spec_id == spec.id)
            )
            for req_child in req_rows.scalars():
                req_child.locked = True
            story_rows = await session.execute(
                select(UserStory).where(UserStory.feature_spec_id == spec.id)
            )
            for story_child in story_rows.scalars():
                story_child.locked = True
            ac_rows = await session.execute(
                select(AcceptanceCriterion).where(AcceptanceCriterion.feature_spec_id == spec.id)
            )
            for ac_child in ac_rows.scalars():
                ac_child.locked = True

        await append_domain_event(
            session,
            aggregate_type="scope",
            aggregate_id=scope_set_id,
            event_type="scope.approved",
            payload={"approval_id": str(approval_id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            delivery_cycle_id=scope_set.delivery_cycle_id,
        )

    async def on_scope_rejected(
        self,
        session: AsyncSession,
        scope_set_id: uuid.UUID,
        approval_id: uuid.UUID,
        ctx: CommandContext,
    ) -> None:
        scope_set = await session.get(ScopeSet, scope_set_id)
        if scope_set is None:
            return
        items = await session.execute(
            select(ScopeSetItem).where(ScopeSetItem.scope_set_id == scope_set_id)
        )
        for item in items.scalars():
            spec = await session.get(FeatureSpec, item.feature_spec_id)
            if spec is None or spec.status == SpecStatus.APPROVED:
                continue
            if spec.status in {SpecStatus.PROPOSED, SpecStatus.DRAFT}:
                spec.status = SpecStatus.REJECTED
        await append_domain_event(
            session,
            aggregate_type="scope",
            aggregate_id=scope_set_id,
            event_type="scope.rejected",
            payload={"approval_id": str(approval_id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            delivery_cycle_id=scope_set.delivery_cycle_id,
        )

    async def approve_single_spec(
        self,
        session: AsyncSession,
        spec_id: uuid.UUID,
        project_id: uuid.UUID,
        delivery_cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> uuid.UUID:
        if ctx.actor.kind != ActorKind.HUMAN or ActorRole.APPROVER not in ctx.actor.roles:
            raise Unauthorized("HUMAN approver required")
        scope_set, approval_id = await self.request_scope_approval(
            session, delivery_cycle_id, [spec_id], project_id, ctx
        )
        from core.domain.enums import ApprovalStatus

        await self._approvals.decide(
            session, approval_id, ApprovalStatus.APPROVED, "single-spec convenience", ctx
        )
        await self.on_scope_approved(session, scope_set.id, approval_id, ctx)
        return approval_id
