"""Provisional baselines tied to accepted known gaps (RL3)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.enums import KnowledgeClass, KnowledgeItemStatus
from core.intelligence.baselines.models import BehavioralBaseline
from core.product_model.models import KnowledgeItem


def _citation_keys(subject_refs: list[Any] | None) -> set[str]:
    keys: set[str] = set()
    for ref in subject_refs or []:
        if not isinstance(ref, dict):
            continue
        for key in ("ref", "path", "stable_key", "key"):
            val = ref.get(key)
            if val:
                keys.add(str(val))
    return keys


async def known_gap_citation_keys(
    session: AsyncSession,
    delivery_cycle_id: uuid.UUID,
) -> set[str]:
    rows = (
        await session.execute(
            select(KnowledgeItem).where(
                KnowledgeItem.delivery_cycle_id == delivery_cycle_id,
                KnowledgeItem.knowledge_class == KnowledgeClass.UNCERTAINTY,
                KnowledgeItem.status == KnowledgeItemStatus.ACTIVE,
            )
        )
    ).scalars()
    keys: set[str] = set()
    for item in rows:
        prov = item.provenance or {}
        if not prov.get("accepted_known_gap"):
            continue
        keys.update(_citation_keys(item.subject_refs))
        keys.update(_citation_keys(item.evidence_refs))
        keys.update(_citation_keys(prov.get("citations")))
    return keys


async def known_gaps_for_baseline(
    session: AsyncSession,
    baseline: BehavioralBaseline,
) -> list[str]:
    """Statements of accepted known gaps (any cycle in the project) the baseline rests on."""
    exercised = {str(k) for k in baseline.exercised_stable_keys or []}
    if not exercised:
        return []
    rows = (
        await session.execute(
            select(KnowledgeItem).where(
                KnowledgeItem.project_id == baseline.project_id,
                KnowledgeItem.knowledge_class == KnowledgeClass.UNCERTAINTY,
                KnowledgeItem.status == KnowledgeItemStatus.ACTIVE,
            )
        )
    ).scalars()
    gaps: list[str] = []
    for item in rows:
        prov = item.provenance or {}
        if not prov.get("accepted_known_gap"):
            continue
        keys = (
            _citation_keys(item.subject_refs)
            | _citation_keys(item.evidence_refs)
            | _citation_keys(prov.get("citations"))
        )
        if keys & exercised:
            gaps.append(item.statement)
    return gaps


async def apply_provisional_if_known_gap(
    session: AsyncSession,
    baseline: BehavioralBaseline,
    delivery_cycle_id: uuid.UUID,
) -> None:
    gap_keys = await known_gap_citation_keys(session, delivery_cycle_id)
    if not gap_keys:
        return
    exercised = {str(k) for k in baseline.exercised_stable_keys or []}
    if exercised & gap_keys:
        baseline.provisional = True
        await session.flush()
