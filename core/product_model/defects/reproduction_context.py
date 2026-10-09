"""Prompt context for ``sentinel.reproduce``: triage plan, index, code."""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.delivery_cycles.models import DeliveryCycle
from core.integration.enums import SpecCodeLinkStatus
from core.intelligence.baselines.characterization_context import (
    code_excerpt,
    index_entities,
    index_summary,
)
from core.intelligence.code_index.enums import EntityType
from core.product_model.defects.models import Defect
from core.product_model.models import Feature, FeatureSpec
from core.traceability.models import SpecCodeLink

_PATH_PARAM = re.compile(r"\{[^}]*\}")


async def build_reproduction_snapshot(
    session: AsyncSession, cycle: DeliveryCycle, defect: Defect
) -> dict[str, Any]:
    triage = defect.triage or {}
    entities = await index_entities(session, cycle)
    routes = _plan_routes(triage)
    linked_keys = await _linked_code_keys(session, cycle, triage)
    linked_keys |= {
        e.stable_key
        for e in entities
        if e.type == EntityType.ROUTE and _route_shape(e.stable_key) in routes
    }
    linked_files = sorted(
        {e.file_path for e in entities if e.stable_key in linked_keys and e.file_path}
    )
    return {
        "triage_json": json.dumps(triage, indent=2),
        "defect_description": defect.description,
        "index_summary": index_summary(entities, linked_keys),
        "code_excerpt": await code_excerpt(session, cycle, linked_files),
    }


def _plan_routes(triage: dict[str, Any]) -> set[str]:
    steps = (triage.get("reproduction_plan") or {}).get("steps") or []
    return {
        _route_shape(f"ROUTE:{str(step['method']).upper()} {step['path']}")
        for step in steps
        if step.get("kind") == "http" and step.get("method") and step.get("path")
    }


def _route_shape(route_key: str) -> str:
    """Triage and the index may name path parameters differently (``{id}`` vs ``{ticket_id}``)."""
    return _PATH_PARAM.sub("{}", route_key)


async def _linked_code_keys(
    session: AsyncSession, cycle: DeliveryCycle, triage: dict[str, Any]
) -> set[str]:
    if cycle.repository_id is None:
        return set()
    spec_keys = {str(k) for k in triage.get("suspected_ac_lineage_keys") or []}
    feature_keys = [str(k) for k in triage.get("feature_keys") or []]
    if feature_keys:
        spec_keys |= set(
            (
                await session.execute(
                    select(FeatureSpec.lineage_key)
                    .join(Feature, Feature.id == FeatureSpec.feature_id)
                    .where(Feature.project_id == cycle.project_id, Feature.key.in_(feature_keys))
                )
            )
            .scalars()
            .all()
        )
    if not spec_keys:
        return set()
    return set(
        (
            await session.execute(
                select(SpecCodeLink.code_stable_key).where(
                    SpecCodeLink.repository_id == cycle.repository_id,
                    SpecCodeLink.spec_lineage_key.in_(spec_keys),
                    SpecCodeLink.status == SpecCodeLinkStatus.ACTIVE,
                )
            )
        )
        .scalars()
        .all()
    )
