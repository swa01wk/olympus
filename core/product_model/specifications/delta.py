"""Deterministic FeatureSpec delta computation and approval pinning."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.approvals.service import ApprovalService
from core.domain.canonical_json import sha256_hex
from core.domain.enums import ApprovalType
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.domain.sequences import next_project_key
from core.intelligence.impact.enums import SpecDeltaStatus
from core.intelligence.impact.models import SpecDelta
from core.product_model.models import AcceptanceCriterion, FeatureSpec, Requirement, UserStory
from core.product_model.schemas import FeatureSpecBody
from core.product_model.specifications.service import FeatureSpecService


def _align_by_lineage(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
    *,
    fields: tuple[str, ...],
) -> dict[str, list[dict[str, Any]]]:
    before_map = {row["lineage_key"]: row for row in before}
    after_map = {row["lineage_key"]: row for row in after}
    added: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    modified: list[dict[str, Any]] = []
    for key, row in after_map.items():
        if key not in before_map:
            added.append(row)
            continue
        prev = before_map[key]
        if any(prev.get(f) != row.get(f) for f in fields):
            modified.append({"before": prev, "after": row, "lineage_key": key})
    for key, row in before_map.items():
        if key not in after_map:
            removed.append(row)
    return {"added": added, "modified": modified, "removed": removed}


def _align_text_lists(before: list[str], after: list[str]) -> dict[str, list[Any]]:
    before_set = list(before)
    after_set = list(after)
    added = [x for x in after_set if x not in before_set]
    removed = [x for x in before_set if x not in after_set]
    modified: list[dict[str, str]] = []
    return {"added": added, "removed": removed, "modified": modified}


class SpecDeltaService:
    async def compute(
        self,
        session: AsyncSession,
        *,
        from_spec_id: uuid.UUID | None,
        to_spec_id: uuid.UUID,
        delivery_cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> SpecDelta:
        to_spec, to_reqs, to_stories, to_acs = await FeatureSpecService().get_with_children(
            session, to_spec_id
        )
        from_reqs: list[Requirement] = []
        from_stories: list[UserStory] = []
        from_acs: list[AcceptanceCriterion] = []
        from_spec: FeatureSpec | None = None
        if from_spec_id is not None:
            svc = FeatureSpecService()
            from_spec, from_reqs, from_stories, from_acs = await svc.get_with_children(
                session, from_spec_id
            )
        if from_spec is not None and from_spec.feature_id != to_spec.feature_id:
            raise DomainError(code="INVALID_INPUT", message="Specs belong to different features")

        to_body = FeatureSpecBody.model_validate(to_spec.body)
        from_body = (
            FeatureSpecBody.model_validate(from_spec.body) if from_spec is not None else None
        )

        changes: dict[str, Any] = {
            "requirements": _align_by_lineage(
                [
                    {
                        "lineage_key": r.lineage_key,
                        "statement": r.statement,
                        "kind": r.kind,
                        "priority": r.priority,
                    }
                    for r in from_reqs
                ],
                [
                    {
                        "lineage_key": r.lineage_key,
                        "statement": r.statement,
                        "kind": r.kind,
                        "priority": r.priority,
                    }
                    for r in to_reqs
                ],
                fields=("statement", "kind", "priority"),
            ),
            "user_stories": _align_by_lineage(
                [
                    {
                        "lineage_key": s.lineage_key,
                        "actor": s.actor,
                        "goal": s.goal,
                        "benefit": s.benefit,
                    }
                    for s in from_stories
                ],
                [
                    {
                        "lineage_key": s.lineage_key,
                        "actor": s.actor,
                        "goal": s.goal,
                        "benefit": s.benefit,
                    }
                    for s in to_stories
                ],
                fields=("actor", "goal", "benefit"),
            ),
            "acceptance_criteria": _align_by_lineage(
                [
                    {
                        "lineage_key": a.lineage_key,
                        "statement": a.statement,
                        "given": a.given,
                        "when": a.when,
                        "then": a.then,
                        "mandatory": a.mandatory,
                    }
                    for a in from_acs
                ],
                [
                    {
                        "lineage_key": a.lineage_key,
                        "statement": a.statement,
                        "given": a.given,
                        "when": a.when,
                        "then": a.then,
                        "mandatory": a.mandatory,
                    }
                    for a in to_acs
                ],
                fields=("statement", "given", "when", "then", "mandatory"),
            ),
        }
        if from_body is not None:
            changes["rules"] = _align_text_lists(from_body.rules, to_body.rules)
            changes["constraints"] = _align_text_lists(from_body.constraints, to_body.constraints)
            changes["inputs"] = _align_text_lists(from_body.inputs, to_body.inputs)
            changes["outputs"] = _align_text_lists(from_body.outputs, to_body.outputs)
        else:
            changes["rules"] = {"added": to_body.rules, "removed": [], "modified": []}
            changes["constraints"] = {
                "added": to_body.constraints,
                "removed": [],
                "modified": [],
            }
            changes["inputs"] = {"added": to_body.inputs, "removed": [], "modified": []}
            changes["outputs"] = {"added": to_body.outputs, "removed": [], "modified": []}

        ac_added = {row["lineage_key"] for row in changes["acceptance_criteria"]["added"]}
        ac_modified = {row["lineage_key"] for row in changes["acceptance_criteria"]["modified"]}
        ac_removed = {row["lineage_key"] for row in changes["acceptance_criteria"]["removed"]}
        for ac in to_acs:
            if ac.lineage_key in ac_added:
                ac.change_kind = "ADDED"
            elif ac.lineage_key in ac_modified:
                ac.change_kind = "MODIFIED"
            elif ac.lineage_key in ac_removed:
                ac.change_kind = "REMOVED"
            else:
                ac.change_kind = None

        content_hash = sha256_hex(changes)
        key = await next_project_key(session, to_spec.project_id, "spec_delta", prefix="SD")
        delta = SpecDelta(
            key=key,
            project_id=to_spec.project_id,
            delivery_cycle_id=delivery_cycle_id,
            feature_id=to_spec.feature_id,
            from_spec_id=from_spec_id,
            to_spec_id=to_spec_id,
            changes=changes,
            content_hash=content_hash,
            status=SpecDeltaStatus.PROPOSED.value,
        )
        session.add(delta)
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="spec_delta",
            aggregate_id=delta.id,
            event_type="spec_delta.computed",
            payload={"content_hash": content_hash, "to_spec_id": str(to_spec_id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=to_spec.project_id,
            delivery_cycle_id=delivery_cycle_id,
        )
        return delta

    async def get(self, session: AsyncSession, delta_id: uuid.UUID) -> SpecDelta:
        row = await session.get(SpecDelta, delta_id)
        if row is None:
            raise DomainError(code="NOT_FOUND", message="SpecDelta not found")
        return row

    async def request_approval(
        self,
        session: AsyncSession,
        delta_id: uuid.UUID,
        ctx: CommandContext,
    ) -> SpecDelta:
        delta = await self.get(session, delta_id)
        if delta.status != SpecDeltaStatus.PROPOSED.value:
            raise DomainError(code="INVALID_STATE", message="SpecDelta not PROPOSED")
        approval = await ApprovalService().request(
            session,
            delta.project_id,
            delta.delivery_cycle_id,
            ApprovalType.SPEC_DELTA,
            subject_type="SPEC_DELTA",
            subject_id=delta.id,
            subject_version=1,
            subject_hash=delta.content_hash,
            ctx=ctx,
        )
        delta.approval_id = approval.id
        await session.flush()
        return delta

    async def mark_approved(
        self,
        session: AsyncSession,
        delta_id: uuid.UUID,
        approval_id: uuid.UUID,
        ctx: CommandContext,
    ) -> SpecDelta:
        delta = await self.get(session, delta_id)
        if delta.approval_id != approval_id:
            raise DomainError(code="INVALID_STATE", message="Approval mismatch")
        if delta.status != SpecDeltaStatus.PROPOSED.value:
            raise DomainError(code="INVALID_STATE", message="SpecDelta not PROPOSED")
        from core.domain.approvals.models import Approval

        approval_row = await session.get(Approval, approval_id)
        if approval_row is None or approval_row.subject_hash != delta.content_hash:
            raise DomainError(code="INVALID_STATE", message="Approval hash mismatch")
        delta.status = SpecDeltaStatus.APPROVED.value
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="spec_delta",
            aggregate_id=delta.id,
            event_type="spec_delta.approved",
            payload={"content_hash": delta.content_hash},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=delta.project_id,
            delivery_cycle_id=delta.delivery_cycle_id,
        )
        return delta

    async def latest_approved_for_cycle(
        self, session: AsyncSession, delivery_cycle_id: uuid.UUID
    ) -> SpecDelta | None:
        result = await session.execute(
            select(SpecDelta)
            .where(
                SpecDelta.delivery_cycle_id == delivery_cycle_id,
                SpecDelta.status == SpecDeltaStatus.APPROVED.value,
            )
            .order_by(SpecDelta.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
