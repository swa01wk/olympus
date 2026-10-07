"""Safe runtime probe templates for GET routes (policy-gated)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.sequences import next_project_key
from core.intelligence.baselines.enums import (
    BaselineCheckKind,
    BaselineSource,
    BaselineStatus,
)
from core.intelligence.baselines.models import BehavioralBaseline
from core.intelligence.code_index.enums import EntityType
from core.intelligence.code_index.models import CodeEntity, CodeIndexVersion
from core.policy.policy_service import get_cached_policy_content
from core.product_model.models import AcceptanceCriterion, FeatureSpec
from core.traceability.models import RepositoryIndexPointer, SpecCodeLink


class SafeRuntimeProbeGenerator:
    def __init__(self) -> None:
        policy = get_cached_policy_content()
        brownfield = policy.get("brownfield") or {}
        self._probes_mode = str(brownfield.get("runtime_probes", "safe_only"))

    async def propose(
        self,
        session: AsyncSession,
        cycle: DeliveryCycle,
        specs: list[FeatureSpec],
        covered_ac_keys: set[tuple[uuid.UUID, str]],
        sha: str,
        ctx: CommandContext,
        *,
        start_seq: int,
    ) -> list[BehavioralBaseline]:
        if self._probes_mode != "safe_only":
            return []
        if cycle.repository_id is None:
            return []
        pointer = await session.get(RepositoryIndexPointer, cycle.repository_id)
        if pointer is None or pointer.canonical_index_version_id is None:
            return []
        version = await session.get(CodeIndexVersion, pointer.canonical_index_version_id)
        if version is None:
            return []
        routes = (
            (
                await session.execute(
                    select(CodeEntity).where(
                        CodeEntity.index_version_id == version.id,
                        CodeEntity.type == EntityType.ROUTE,
                    )
                )
            )
            .scalars()
            .all()
        )
        safe_routes = []
        for route in routes:
            meta = route.entity_metadata or {}
            method = str(meta.get("method", "GET")).upper()
            if method != "GET":
                continue
            safe_routes.append(route)
        if not safe_routes:
            return []
        out: list[BehavioralBaseline] = []
        seq = start_seq
        for spec in specs:
            acs = (
                (
                    await session.execute(
                        select(AcceptanceCriterion).where(
                            AcceptanceCriterion.feature_spec_id == spec.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            links = (
                (await session.execute(select(SpecCodeLink).where(SpecCodeLink.spec_id == spec.id)))
                .scalars()
                .all()
            )
            link_keys = {link.code_stable_key for link in links}
            for ac in acs:
                if (spec.id, ac.lineage_key) in covered_ac_keys:
                    continue
                picked = _pick_route(safe_routes, link_keys)
                if picked is None:
                    continue
                route = picked
                meta = route.entity_metadata or {}
                path = str(meta.get("path") or route.qualified_name)
                seq += 1
                key = await next_project_key(session, cycle.project_id, "baseline", prefix="BL")
                row = BehavioralBaseline(
                    project_id=cycle.project_id,
                    lineage_key=key,
                    version=1,
                    status=BaselineStatus.PROPOSED,
                    source=BaselineSource.BROWNFIELD_RUNTIME_PROBE,
                    given=f"Service at {sha}",
                    when=f"GET {path}",
                    then="Response status and JSON shape match onboarding observation",
                    check_kind=BaselineCheckKind.API_PROBE,
                    check_ref=f"GET:{path}",
                    feature_spec_id=spec.id,
                    ac_lineage_key=ac.lineage_key,
                    observed_behavior_ids=[],
                    exercised_stable_keys=[route.stable_key],
                    established_sha=sha,
                )
                session.add(row)
                await session.flush()
                out.append(row)
                covered_ac_keys.add((spec.id, ac.lineage_key))
        return out


def _pick_route(routes: list[CodeEntity], link_keys: set[str]) -> CodeEntity | None:
    for route in routes:
        if route.stable_key in link_keys:
            return route
    return routes[0] if routes else None
