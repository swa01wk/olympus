"""Load magnified subject context for orchestrator chat snapshots."""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import SpecStatus
from core.intelligence.impact.models import ImpactAssessment, SpecDelta
from core.planning.models import Architecture, ImplementationSpec, TaskPlanRow
from core.product_model.changes.models import ChangeRequest
from core.product_model.defects.models import Defect, RootCauseAnalysis
from core.product_model.models import Feature, FeatureSpec, ProductSource, ScopeSet, ScopeSetItem
from core.release.models import Release
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

FOCUS_SUBJECT_TYPES = frozenset(
    {
        "product_source",
        "feature_spec",
        "scope_set",
        "architecture",
        "implementation_spec",
        "task_plan",
        "spec_delta",
        "impact_assessment",
        "defect",
        "release",
    }
)

FOCUS_CHAR_LIMIT = 24_000

FocusLoader = Callable[[AsyncSession, uuid.UUID], Awaitable[dict[str, Any] | None]]


def apply_focus_cap(payload: dict[str, Any]) -> dict[str, Any]:
    if _json_size(payload) <= FOCUS_CHAR_LIMIT:
        return payload
    out = dict(payload)
    out["truncated"] = True
    sources: Any = out.get("sources")
    while _json_size(out) > FOCUS_CHAR_LIMIT:
        if isinstance(sources, str) and sources:
            sources = sources[: max(0, len(sources) - 800)]
        elif isinstance(sources, list) and sources:
            sources = sources[:-1]
        else:
            body = out.get("body")
            if isinstance(body, dict) and body:
                out["body"] = {"summary": str(body.get("summary", ""))[:2000]}
            elif isinstance(body, str) and body:
                out["body"] = body[:2000]
            else:
                break
        out["sources"] = sources
    return out


def _json_size(obj: Any) -> int:
    return len(json.dumps(obj, default=str))


async def load_focus(
    session: AsyncSession,
    subject_type: str,
    subject_id: uuid.UUID,
) -> dict[str, Any] | None:
    if subject_type not in FOCUS_SUBJECT_TYPES:
        return None
    loader = _LOADERS.get(subject_type)
    if loader is None:
        return None
    raw = await loader(session, subject_id)
    if raw is None:
        return None
    return apply_focus_cap(raw)


async def _load_product_source(
    session: AsyncSession, subject_id: uuid.UUID
) -> dict[str, Any] | None:
    row = await session.get(ProductSource, subject_id)
    if row is None:
        return None
    return {
        "type": "product_source",
        "id": str(row.id),
        "key": row.lineage_key,
        "version": row.version,
        "status": row.source_type,
        "content_hash": row.content_hash,
        "body": {"title": row.title, "mime_type": row.mime_type},
        "sources": f"PRD {row.lineage_key} v{row.version}: {row.title}",
    }


async def _load_feature_spec(session: AsyncSession, subject_id: uuid.UUID) -> dict[str, Any] | None:
    spec = await session.get(FeatureSpec, subject_id)
    if spec is None:
        return None
    feat = await session.get(Feature, spec.feature_id)
    sections: list[str] = []
    if feat is not None:
        for ref in feat.source_refs or []:
            if isinstance(ref, dict) and ref.get("section"):
                sections.append(str(ref["section"]))
    if not sections and spec.derived_from_source_version_id:
        src = await session.get(ProductSource, spec.derived_from_source_version_id)
        if src is not None:
            sections.append(f"{src.title} (v{src.version})")
    return {
        "type": "feature_spec",
        "id": str(spec.id),
        "key": spec.lineage_key,
        "version": spec.version,
        "status": spec.status.value,
        "content_hash": spec.content_hash,
        "body": spec.body,
        "sources": sections,
    }


async def _load_scope_set(session: AsyncSession, subject_id: uuid.UUID) -> dict[str, Any] | None:
    row = await session.get(ScopeSet, subject_id)
    if row is None:
        return None
    items = (
        await session.execute(select(ScopeSetItem).where(ScopeSetItem.scope_set_id == row.id))
    ).scalars()
    keys: list[str] = []
    for item in items:
        spec = await session.get(FeatureSpec, item.feature_spec_id)
        if spec is not None:
            keys.append(spec.lineage_key)
    return {
        "type": "scope_set",
        "id": str(row.id),
        "key": str(row.id)[:8],
        "version": 1,
        "status": "PROPOSED",
        "content_hash": row.content_hash,
        "body": {"feature_spec_keys": keys},
        "sources": keys,
    }


async def _load_architecture(session: AsyncSession, subject_id: uuid.UUID) -> dict[str, Any] | None:
    arch = await session.get(Architecture, subject_id)
    if arch is None:
        return None
    approved_specs = (
        await session.execute(
            select(FeatureSpec).where(
                FeatureSpec.project_id == arch.project_id,
                FeatureSpec.status == SpecStatus.APPROVED,
            )
        )
    ).scalars()
    sources = [
        {"key": s.lineage_key, "summary": (s.body or {}).get("summary", "")} for s in approved_specs
    ]
    return {
        "type": "architecture",
        "id": str(arch.id),
        "key": arch.lineage_key,
        "version": arch.version,
        "status": arch.status.value,
        "content_hash": arch.content_hash,
        "body": arch.body,
        "sources": sources,
    }


async def _load_implementation_spec(
    session: AsyncSession, subject_id: uuid.UUID
) -> dict[str, Any] | None:
    row = await session.get(ImplementationSpec, subject_id)
    if row is None:
        return None
    feat_spec = await session.get(FeatureSpec, row.feature_spec_id)
    arch = await session.get(Architecture, row.architecture_id)
    return {
        "type": "implementation_spec",
        "id": str(row.id),
        "key": row.lineage_key,
        "version": row.version,
        "status": row.status.value,
        "content_hash": row.content_hash,
        "body": row.body,
        "sources": {
            "feature_spec": feat_spec.lineage_key if feat_spec else None,
            "architecture_refs": (row.body or {}).get("architecture_refs", []),
            "architecture_key": arch.lineage_key if arch else None,
        },
    }


async def _load_task_plan(session: AsyncSession, subject_id: uuid.UUID) -> dict[str, Any] | None:
    row = await session.get(TaskPlanRow, subject_id)
    if row is None:
        return None
    impl_keys: list[str] = []
    for raw_id in row.implementation_spec_ids or []:
        impl = await session.get(ImplementationSpec, uuid.UUID(str(raw_id)))
        if impl is not None:
            impl_keys.append(impl.lineage_key)
    return {
        "type": "task_plan",
        "id": str(row.id),
        "key": str(row.id)[:8],
        "version": 1,
        "status": row.status,
        "content_hash": "",
        "body": row.body,
        "sources": impl_keys,
    }


async def _load_spec_delta(session: AsyncSession, subject_id: uuid.UUID) -> dict[str, Any] | None:
    delta = await session.get(SpecDelta, subject_id)
    if delta is None:
        return None
    cr = (
        await session.execute(
            select(ChangeRequest).where(ChangeRequest.delivery_cycle_id == delta.delivery_cycle_id)
        )
    ).scalar_one_or_none()
    return {
        "type": "spec_delta",
        "id": str(delta.id),
        "key": delta.key,
        "version": 1,
        "status": delta.status,
        "content_hash": delta.content_hash,
        "body": delta.changes,
        "sources": (cr.description if cr is not None else ""),
    }


async def _load_impact_assessment(
    session: AsyncSession, subject_id: uuid.UUID
) -> dict[str, Any] | None:
    row = await session.get(ImpactAssessment, subject_id)
    if row is None:
        return None
    return {
        "type": "impact_assessment",
        "id": str(row.id),
        "key": row.key,
        "version": 1,
        "status": row.status,
        "content_hash": row.content_hash,
        "body": row.summary,
        "sources": {
            "architecture_delta_suggested": row.architecture_delta_suggested,
            "seed_kind": row.seed_kind,
        },
    }


async def _load_defect(session: AsyncSession, subject_id: uuid.UUID) -> dict[str, Any] | None:
    defect = await session.get(Defect, subject_id)
    if defect is None:
        return None
    rca = (
        await session.execute(
            select(RootCauseAnalysis)
            .where(RootCauseAnalysis.defect_id == defect.id)
            .order_by(RootCauseAnalysis.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return {
        "type": "defect",
        "id": str(defect.id),
        "key": defect.key,
        "version": 1,
        "status": defect.status,
        "content_hash": "",
        "body": {
            "title": defect.title,
            "description": defect.description,
            "triage": defect.triage or {},
            "expected_ac_ids": defect.expected_ac_ids or [],
        },
        "sources": {
            "triage": defect.triage or {},
            "expected_ac_ids": defect.expected_ac_ids or [],
            "root_cause": rca.explanation if rca else "",
        },
    }


async def _load_release(session: AsyncSession, subject_id: uuid.UUID) -> dict[str, Any] | None:
    row = await session.get(Release, subject_id)
    if row is None:
        return None
    return {
        "type": "release",
        "id": str(row.id),
        "key": row.key,
        "version": 1,
        "status": row.status.value,
        "content_hash": row.integrated_sha,
        "body": {"integrated_sha": row.integrated_sha, "tag": row.tag},
        "sources": f"cycle {row.delivery_cycle_id}",
    }


_LOADERS: dict[str, FocusLoader] = {
    "product_source": _load_product_source,
    "feature_spec": _load_feature_spec,
    "scope_set": _load_scope_set,
    "architecture": _load_architecture,
    "implementation_spec": _load_implementation_spec,
    "task_plan": _load_task_plan,
    "spec_delta": _load_spec_delta,
    "impact_assessment": _load_impact_assessment,
    "defect": _load_defect,
    "release": _load_release,
}


async def resolve_cycle_project_id(
    session: AsyncSession, delivery_cycle_id: uuid.UUID
) -> uuid.UUID | None:
    cycle = await session.get(DeliveryCycle, delivery_cycle_id)
    return cycle.project_id if cycle else None
