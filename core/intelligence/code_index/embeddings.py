"""Lazy embedding storage keyed by content hash (Phase 13)."""

from __future__ import annotations

import math
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.domain.canonical_json import sha256_hex
from core.intelligence.code_index.models import CodeEntity
from core.intelligence.impact.models import Embedding
from core.runtime.contracts import EmbeddingRequest
from core.runtime.model_router import ModelRouter


def entity_embedding_text(entity: CodeEntity, source: str | None = None) -> str:
    meta = entity.entity_metadata or {}
    sig = meta.get("signature", "")
    doc = meta.get("docstring", "")
    head = (source or "").splitlines()[:8]
    return "\n".join(
        [
            entity.qualified_name,
            sig,
            doc,
            *head,
        ]
    ).strip()


class EmbeddingService:
    def __init__(self, router: ModelRouter | None = None) -> None:
        self._router = router

    async def embed_texts(
        self,
        session: AsyncSession,
        *,
        subject_type: str,
        subject_key: str,
        content_hash: str,
        texts: list[str],
        repository_id: uuid.UUID | None,
        metadata: dict[str, Any] | None = None,
    ) -> list[list[float]] | None:
        settings = get_settings()
        model = settings.model_embedding or "text-embedding-3-small"
        existing = await session.execute(
            select(Embedding).where(
                Embedding.subject_type == subject_type,
                Embedding.subject_key == subject_key,
                Embedding.content_hash == content_hash,
                Embedding.model == model,
            )
        )
        row = existing.scalar_one_or_none()
        if row is not None:
            return [list(row.vector)]

        if self._router is None:
            return None
        try:
            result = await self._router.embed(
                EmbeddingRequest(alias="embedding", texts=texts, metadata=metadata or {})
            )
        except Exception:
            return None
        vectors = result.vectors
        if not vectors:
            return None
        dim = len(vectors[0])
        if any(math.isnan(v) for vec in vectors for v in vec):
            return None
        for vec in vectors:
            session.add(
                Embedding(
                    subject_type=subject_type,
                    subject_key=subject_key,
                    repository_id=repository_id,
                    content_hash=content_hash,
                    model=model,
                    dim=dim,
                    vector=vec,
                )
            )
        await session.flush()
        return vectors

    async def entity_vector(
        self,
        session: AsyncSession,
        entity: CodeEntity,
        source: str | None,
        repository_id: uuid.UUID,
        metadata: dict[str, Any] | None = None,
    ) -> list[float] | None:
        text = entity_embedding_text(entity, source)
        if not text.strip():
            return None
        content_hash = entity.content_hash or sha256_hex({"text": text})
        vecs = await self.embed_texts(
            session,
            subject_type="CODE_ENTITY",
            subject_key=entity.stable_key,
            content_hash=content_hash,
            texts=[text],
            repository_id=repository_id,
            metadata=metadata,
        )
        return vecs[0] if vecs else None
