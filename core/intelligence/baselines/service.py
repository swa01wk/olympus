"""Baseline activation and review queue helpers."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.enums import EvidenceResult
from core.assurance.models import Evidence
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import KnowledgeClass, SpecKind, SpecStatus
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.intelligence.baselines.enums import BaselineActivation, BaselineStatus
from core.intelligence.baselines.models import BehavioralBaseline, PromotionDecision
from core.planning.models import Architecture, ImplementationSpec
from core.policy.policy_service import get_cached_policy_content
from core.product_model.models import FeatureSpec, KnowledgeItem


class BaselineService:
    async def activate_human(
        self,
        session: AsyncSession,
        baseline_id: uuid.UUID,
        ctx: CommandContext,
    ) -> BehavioralBaseline:
        bl = await session.get(BehavioralBaseline, baseline_id)
        if bl is None:
            raise DomainError(code="NOT_FOUND", message="Baseline not found")
        return await self._activate(session, bl, BaselineActivation.HUMAN, ctx)

    async def try_auto_activate_for_spec(
        self,
        session: AsyncSession,
        feature_spec_id: uuid.UUID,
        ctx: CommandContext,
    ) -> list[BehavioralBaseline]:
        policy = get_cached_policy_content()
        baselines_cfg = policy.get("baselines") or {}
        if not baselines_cfg.get("auto_activate_on_pass", False):
            return []
        spec = await session.get(FeatureSpec, feature_spec_id)
        if spec is None:
            return []
        allowed = (
            SpecStatus.APPROVED,
            SpecStatus.PROMOTED,
            SpecStatus.CONFIRMED_EXISTING,
        )
        if spec.status not in allowed and not (
            spec.spec_kind == SpecKind.CANONICAL and spec.status == SpecStatus.APPROVED
        ):
            return []
        rows = (
            (
                await session.execute(
                    select(BehavioralBaseline).where(
                        BehavioralBaseline.feature_spec_id == feature_spec_id,
                        BehavioralBaseline.status == BaselineStatus.PROPOSED,
                    )
                )
            )
            .scalars()
            .all()
        )
        activated: list[BehavioralBaseline] = []
        for bl in rows:
            if await self._can_activate(session, bl):
                activated.append(
                    await self._activate(session, bl, BaselineActivation.AUTO_DETERMINISTIC, ctx)
                )
        return activated

    async def _can_activate(self, session: AsyncSession, bl: BehavioralBaseline) -> bool:
        if bl.status == BaselineStatus.FAILED_AT_BASE:
            return False
        if bl.established_evidence_id is None:
            return False
        ev = await session.get(Evidence, bl.established_evidence_id)
        return ev is not None and ev.result == EvidenceResult.PASS

    async def _activate(
        self,
        session: AsyncSession,
        bl: BehavioralBaseline,
        activation: BaselineActivation,
        ctx: CommandContext,
    ) -> BehavioralBaseline:
        if bl.status == BaselineStatus.FAILED_AT_BASE:
            raise DomainError(
                code="BASELINE_FAILED_AT_BASE",
                message="Cannot activate baseline that failed at base SHA",
            )
        if not await self._can_activate(session, bl):
            raise DomainError(
                code="EVIDENCE_REQUIRED",
                message="Baseline requires PASS evidence at established SHA",
            )
        bl.status = BaselineStatus.ACTIVE
        bl.activation = activation
        await session.flush()
        cycle = (
            await session.execute(
                select(DeliveryCycle)
                .where(DeliveryCycle.project_id == bl.project_id)
                .order_by(DeliveryCycle.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        await append_domain_event(
            session,
            aggregate_type="baseline",
            aggregate_id=bl.id,
            event_type="baseline.activated",
            payload={"activation": activation.value},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=bl.project_id,
            delivery_cycle_id=cycle.id if cycle else None,
        )
        return bl

    async def review_queue(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None:
            raise DomainError(code="NOT_FOUND", message="Cycle not found")
        decisions = {
            (d.subject_type, d.subject_id): d
            for d in (
                await session.execute(
                    select(PromotionDecision).where(PromotionDecision.delivery_cycle_id == cycle_id)
                )
            ).scalars()
        }
        items: list[dict[str, Any]] = []
        specs = (
            (
                await session.execute(
                    select(FeatureSpec).where(
                        FeatureSpec.project_id == cycle.project_id,
                        FeatureSpec.spec_kind == SpecKind.RECOVERED,
                        FeatureSpec.status == SpecStatus.PROPOSED,
                    )
                )
            )
            .scalars()
            .all()
        )
        for spec in specs:
            items.append(
                _queue_item(
                    "FEATURE_SPEC",
                    spec.id,
                    {
                        "lineage_key": spec.lineage_key,
                        "confidence": spec.confidence,
                        "claimed_confidence": spec.claimed_confidence,
                    },
                    decisions.get(("FEATURE_SPEC", spec.id)),
                )
            )
        baselines = (
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
        for bl in baselines:
            items.append(
                _queue_item(
                    "BASELINE",
                    bl.id,
                    {
                        "lineage_key": bl.lineage_key,
                        "check_ref": bl.check_ref,
                        "source": bl.source.value,
                    },
                    decisions.get(("BASELINE", bl.id)),
                )
            )
        arch = (
            await session.execute(
                select(Architecture)
                .where(
                    Architecture.project_id == cycle.project_id,
                    Architecture.kind == "RECOVERED",
                    Architecture.status == SpecStatus.PROPOSED,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if arch:
            items.append(
                _queue_item(
                    "ARCHITECTURE",
                    arch.id,
                    {"version": arch.version},
                    decisions.get(("ARCHITECTURE", arch.id)),
                )
            )
        impls = (
            (
                await session.execute(
                    select(ImplementationSpec).where(
                        ImplementationSpec.project_id == cycle.project_id,
                        ImplementationSpec.kind == "RECOVERED",
                        ImplementationSpec.status == SpecStatus.PROPOSED,
                    )
                )
            )
            .scalars()
            .all()
        )
        for impl in impls:
            items.append(
                _queue_item(
                    "IMPLEMENTATION_SPEC",
                    impl.id,
                    {"lineage_key": impl.lineage_key},
                    decisions.get(("IMPLEMENTATION_SPEC", impl.id)),
                )
            )
        uncertainties = (
            (
                await session.execute(
                    select(KnowledgeItem).where(
                        KnowledgeItem.delivery_cycle_id == cycle_id,
                        KnowledgeItem.knowledge_class == KnowledgeClass.UNCERTAINTY,
                    )
                )
            )
            .scalars()
            .all()
        )
        for unc in uncertainties:
            if (unc.provenance or {}).get("accepted_known_gap"):
                continue
            items.append(
                _queue_item(
                    "UNCERTAINTY",
                    unc.id,
                    {"statement": unc.statement},
                    decisions.get(("UNCERTAINTY", unc.id)),
                )
            )
        return items


def _queue_item(
    subject_type: str,
    subject_id: uuid.UUID,
    detail: dict[str, Any],
    decision: PromotionDecision | None,
) -> dict[str, Any]:
    return {
        "subject_type": subject_type,
        "subject_id": str(subject_id),
        "detail": detail,
        "decided": decision is not None,
        "decision": decision.decision if decision else None,
    }
