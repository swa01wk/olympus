"""Policy-configured BFS over CodeRelations with path and confidence recording."""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.intelligence.code_index.enums import EntityType, RelationType
from core.intelligence.code_index.models import CodeEntity, CodeRelation
from core.policy.policy_service import get_cached_policy_content


@dataclass
class TraversalEdge:
    relation: RelationType
    direction: str
    depth: int


@dataclass
class TraversalHit:
    entity: CodeEntity
    impact_kind: str
    path: list[dict[str, str]] = field(default_factory=list)
    confidence: float = 1.0
    contract_surface: bool = False


CONTRACT_TYPES = frozenset(
    {
        EntityType.SCHEMA,
        EntityType.ROUTE,
        EntityType.ORM_MODEL,
        EntityType.TABLE,
    }
)


def default_traversal_policy() -> list[TraversalEdge]:
    policy = get_cached_policy_content().get("impact", {}).get("traversal", {})
    edges_cfg = policy.get("edges")
    if edges_cfg:
        out: list[TraversalEdge] = []
        for row in edges_cfg:
            out.append(
                TraversalEdge(
                    relation=RelationType(row["relation"]),
                    direction=row.get("direction", "both"),
                    depth=int(row.get("depth", 1)),
                )
            )
        return out
    return [
        TraversalEdge(RelationType.CALLS, "in", 2),
        TraversalEdge(RelationType.CALLS, "out", 1),
        TraversalEdge(RelationType.IMPORTS, "in", 1),
        TraversalEdge(RelationType.EXPOSES, "both", 1),
        TraversalEdge(RelationType.USES_SCHEMA, "both", 1),
        TraversalEdge(RelationType.MAPS_TO, "both", 1),
        TraversalEdge(RelationType.ACCESSES, "both", 1),
        TraversalEdge(RelationType.INHERITS, "both", 1),
    ]


class ImpactTraversal:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _adjacent(
        self,
        index_version_id: uuid.UUID,
        entity_id: uuid.UUID,
        relation: RelationType,
        direction: str,
    ) -> list[tuple[CodeRelation, CodeEntity, str]]:
        out: list[tuple[CodeRelation, CodeEntity, str]] = []
        if direction in {"out", "both"}:
            q = (
                select(CodeRelation, CodeEntity)
                .join(CodeEntity, CodeRelation.target_entity_id == CodeEntity.id)
                .where(
                    CodeRelation.index_version_id == index_version_id,
                    CodeRelation.source_entity_id == entity_id,
                    CodeRelation.relation == relation,
                )
            )
            for rel, ent in (await self._session.execute(q)).all():
                out.append((rel, ent, "out"))
        if direction in {"in", "both"}:
            q = (
                select(CodeRelation, CodeEntity)
                .join(CodeEntity, CodeRelation.source_entity_id == CodeEntity.id)
                .where(
                    CodeRelation.index_version_id == index_version_id,
                    CodeRelation.target_entity_id == entity_id,
                    CodeRelation.relation == relation,
                )
            )
            for rel, ent in (await self._session.execute(q)).all():
                out.append((rel, ent, "in"))
        return out

    async def expand(
        self,
        index_version_id: uuid.UUID,
        seed_keys: set[str],
        *,
        link_confidence: dict[str, float] | None = None,
    ) -> dict[str, TraversalHit]:
        link_confidence = link_confidence or {}
        entities = await self._session.execute(
            select(CodeEntity).where(CodeEntity.index_version_id == index_version_id)
        )
        by_key = {e.stable_key: e for e in entities.scalars()}
        hits: dict[str, TraversalHit] = {}
        for sk in seed_keys:
            ent = by_key.get(sk)
            if ent is None:
                continue
            hits[sk] = TraversalHit(
                entity=ent,
                impact_kind="DIRECT",
                path=[],
                confidence=link_confidence.get(sk, 1.0),
                contract_surface=ent.type in CONTRACT_TYPES,
            )

        for edge in default_traversal_policy():
            for seed_key in seed_keys:
                start = by_key.get(seed_key)
                if start is None:
                    continue
                queue: deque[tuple[uuid.UUID, int, list[dict[str, str]], float]] = deque(
                    [(start.id, 0, [], link_confidence.get(seed_key, 1.0))]
                )
                seen: set[tuple[uuid.UUID, int]] = {(start.id, 0)}
                while queue:
                    node_id, dist, path, conf = queue.popleft()
                    if dist >= edge.depth:
                        continue
                    node = await self._session.get(CodeEntity, node_id)
                    if node is None:
                        continue
                    for rel, neighbor, _dir in await self._adjacent(
                        index_version_id, node_id, edge.relation, edge.direction
                    ):
                        step = {
                            "from": node.stable_key,
                            "relation": edge.relation.value,
                            "to": neighbor.stable_key,
                        }
                        new_path = path + [step]
                        new_conf = conf * rel.confidence
                        kind = "DIRECT" if neighbor.stable_key in seed_keys else "TRANSITIVE"
                        prev = hits.get(neighbor.stable_key)
                        if prev is None or prev.confidence < new_conf:
                            hits[neighbor.stable_key] = TraversalHit(
                                entity=neighbor,
                                impact_kind=kind,
                                path=new_path,
                                confidence=new_conf,
                                contract_surface=neighbor.type in CONTRACT_TYPES,
                            )
                        nd = dist + 1
                        if nd <= edge.depth and (neighbor.id, nd) not in seen:
                            seen.add((neighbor.id, nd))
                            queue.append((neighbor.id, nd, new_path, new_conf))
        return hits
