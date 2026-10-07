from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.intelligence.code_index.enums import EntityType
from core.intelligence.code_index.models import CodeEntity, CodeIndexVersion
from core.intelligence.code_index.retrieval.types import RetrievalHit


class LexicalRetrieval:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search(
        self,
        index_version_id: uuid.UUID,
        q: str,
        mode: str = "symbol",
        limit: int = 20,
    ) -> list[RetrievalHit]:
        limit = max(1, min(limit, 100))
        version = await self._session.get(CodeIndexVersion, index_version_id)
        if version is None:
            return []

        query = q.strip()
        if not query:
            return []

        stmt = select(CodeEntity).where(CodeEntity.index_version_id == index_version_id)

        if mode == "route":
            stmt = stmt.where(
                CodeEntity.type == EntityType.ROUTE,
                or_(
                    CodeEntity.qualified_name.ilike(f"%{query}%"),
                    func.coalesce(CodeEntity.entity_metadata["path"].astext, "").ilike(
                        f"%{query}%"
                    ),
                ),
            )
        elif mode == "lexical":
            pattern = f"%{query}%"
            stmt = stmt.where(
                or_(
                    CodeEntity.qualified_name.ilike(pattern),
                    func.coalesce(CodeEntity.file_path, "").ilike(pattern),
                )
            )
        else:
            stmt = stmt.where(
                CodeEntity.qualified_name.op("%")(query),
            )

        stmt = stmt.limit(limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        hits: list[RetrievalHit] = []
        for row in rows:
            score = 1.0
            if mode == "symbol" and query.lower() in row.qualified_name.lower():
                score = 0.9 + min(0.1, len(query) / max(len(row.qualified_name), 1))
            hits.append(
                RetrievalHit(
                    entity_id=row.id,
                    stable_key=row.stable_key,
                    type=row.type,
                    retrieval_source="LEXICAL",
                    score=score,
                    provenance=[f"lexical:{mode}"],
                    index_version_id=version.id,
                    commit_sha=version.commit_sha,
                    qualified_name=row.qualified_name,
                    file_path=row.file_path,
                )
            )
        hits.sort(key=lambda h: (-h.score, h.stable_key))
        return hits
