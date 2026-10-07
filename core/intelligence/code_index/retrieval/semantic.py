"""pgvector cosine similarity retrieval."""

from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.intelligence.code_index.models import CodeEntity, CodeIndexVersion
from core.intelligence.code_index.retrieval.types import RetrievalHit


class SemanticRetrieval:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search(
        self,
        index_version_id: uuid.UUID,
        query_vector: list[float],
        *,
        limit: int = 20,
    ) -> list[RetrievalHit]:
        if not query_vector:
            return []
        vec_literal = "[" + ",".join(str(float(v)) for v in query_vector) + "]"
        rows = await self._session.execute(
            text(
                """
                SELECT e.subject_key, 1 - (e.vector <=> :q::vector) AS score
                FROM embeddings e
                WHERE e.subject_type = 'CODE_ENTITY'
                ORDER BY e.vector <=> :q::vector
                LIMIT :lim
                """
            ),
            {"q": vec_literal, "lim": limit},
        )
        hits: list[RetrievalHit] = []
        version = await self._session.get(CodeIndexVersion, index_version_id)
        if version is None:
            return []
        for subject_key, score in rows.all():
            ent_row = await self._session.execute(
                select(CodeEntity).where(
                    CodeEntity.index_version_id == index_version_id,
                    CodeEntity.stable_key == subject_key,
                )
            )
            ent = ent_row.scalar_one_or_none()
            if ent is None:
                continue
            hits.append(
                RetrievalHit(
                    entity_id=ent.id,
                    stable_key=ent.stable_key,
                    type=ent.type,
                    retrieval_source="SEMANTIC",
                    score=float(score),
                    path=[],
                    provenance=["semantic:cosine"],
                    index_version_id=index_version_id,
                    commit_sha=version.commit_sha,
                    qualified_name=ent.qualified_name,
                    file_path=ent.file_path,
                )
            )
        return hits
