from __future__ import annotations

import uuid
from collections import deque

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.intelligence.code_index.enums import RelationType
from core.intelligence.code_index.models import CodeEntity, CodeIndexVersion, CodeRelation
from core.intelligence.code_index.retrieval.types import RetrievalHit


class StructuralRetrieval:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def neighbors(
        self,
        entity_id: uuid.UUID,
        relations: set[RelationType] | None = None,
        direction: str = "both",
        depth: int = 1,
    ) -> list[RetrievalHit]:
        depth = max(1, min(depth, 4))
        entity = await self._session.get(CodeEntity, entity_id)
        if entity is None:
            return []
        version = await self._session.get(CodeIndexVersion, entity.index_version_id)
        if version is None:
            return []

        frontier: set[tuple[uuid.UUID, int, tuple[str, ...]]] = {
            (entity_id, 0, (entity.stable_key,))
        }
        seen: set[uuid.UUID] = {entity_id}
        hits: list[RetrievalHit] = []

        while frontier:
            next_frontier: set[tuple[uuid.UUID, int, tuple[str, ...]]] = set()
            for node_id, dist, path in frontier:
                if dist >= depth:
                    continue
                for rel_row, neighbor, edge_dir in await self._adjacent(
                    node_id, relations, direction
                ):
                    if neighbor.id in seen:
                        continue
                    seen.add(neighbor.id)
                    new_path = path + (neighbor.stable_key,)
                    hits.append(
                        RetrievalHit(
                            entity_id=neighbor.id,
                            stable_key=neighbor.stable_key,
                            type=neighbor.type,
                            retrieval_source="STRUCTURAL",
                            score=1.0 / (dist + 1),
                            path=list(new_path),
                            provenance=[
                                f"{edge_dir}:{rel_row.relation.value}:{rel_row.provenance}"
                            ],
                            index_version_id=version.id,
                            commit_sha=version.commit_sha,
                            qualified_name=neighbor.qualified_name,
                            file_path=neighbor.file_path,
                        )
                    )
                    if dist + 1 < depth:
                        next_frontier.add((neighbor.id, dist + 1, new_path))
            frontier = next_frontier

        return hits

    async def path(
        self,
        from_id: uuid.UUID,
        to_id: uuid.UUID,
        relations: set[RelationType] | None = None,
        max_depth: int = 6,
    ) -> list[RetrievalHit] | None:
        max_depth = max(1, min(max_depth, 6))
        start = await self._session.get(CodeEntity, from_id)
        end = await self._session.get(CodeEntity, to_id)
        if start is None or end is None:
            return None
        version = await self._session.get(CodeIndexVersion, start.index_version_id)
        if version is None:
            return None

        queue: deque[tuple[uuid.UUID, list[RetrievalHit]]] = deque([(from_id, [])])
        visited: set[uuid.UUID] = {from_id}

        while queue:
            node_id, path_hits = queue.popleft()
            if len(path_hits) >= max_depth:
                continue
            for rel_row, neighbor, edge_dir in await self._adjacent(node_id, relations, "both"):
                if neighbor.id in visited:
                    continue
                hit = RetrievalHit(
                    entity_id=neighbor.id,
                    stable_key=neighbor.stable_key,
                    type=neighbor.type,
                    retrieval_source="STRUCTURAL",
                    score=1.0,
                    path=[h.stable_key for h in path_hits] + [neighbor.stable_key],
                    provenance=[f"{edge_dir}:{rel_row.relation.value}"],
                    index_version_id=version.id,
                    commit_sha=version.commit_sha,
                    qualified_name=neighbor.qualified_name,
                    file_path=neighbor.file_path,
                )
                if neighbor.id == to_id:
                    return path_hits + [hit]
                visited.add(neighbor.id)
                queue.append((neighbor.id, path_hits + [hit]))
        return None

    async def _adjacent(
        self,
        entity_id: uuid.UUID,
        relations: set[RelationType] | None,
        direction: str,
    ) -> list[tuple[CodeRelation, CodeEntity, str]]:
        out: list[tuple[CodeRelation, CodeEntity, str]] = []
        if direction in {"out", "both"}:
            q = (
                select(CodeRelation, CodeEntity)
                .join(CodeEntity, CodeRelation.target_entity_id == CodeEntity.id)
                .where(CodeRelation.source_entity_id == entity_id)
            )
            if relations:
                q = q.where(CodeRelation.relation.in_(relations))
            for rel, ent in (await self._session.execute(q)).all():
                out.append((rel, ent, "out"))
        if direction in {"in", "both"}:
            q = (
                select(CodeRelation, CodeEntity)
                .join(CodeEntity, CodeRelation.source_entity_id == CodeEntity.id)
                .where(CodeRelation.target_entity_id == entity_id)
            )
            if relations:
                q = q.where(CodeRelation.relation.in_(relations))
            for rel, ent in (await self._session.execute(q)).all():
                out.append((rel, ent, "in"))
        return out
