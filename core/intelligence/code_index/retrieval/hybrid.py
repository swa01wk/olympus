"""Structural → lexical → semantic retrieval orchestration."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.canonical_json import sha256_hex
from core.intelligence.code_index.embeddings import EmbeddingService
from core.intelligence.code_index.retrieval.lexical import LexicalRetrieval
from core.intelligence.code_index.retrieval.semantic import SemanticRetrieval
from core.intelligence.code_index.retrieval.structural import StructuralRetrieval
from core.intelligence.code_index.retrieval.types import RetrievalHit, RetrievalSource
from core.product_model.models import Feature, FeatureSpec


class FeatureCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_id: uuid.UUID
    feature_key: str
    spec_id: uuid.UUID
    spec_lineage_key: str
    score: float
    retrieval_source: RetrievalSource


class HybridRetrieval:
    def __init__(
        self, session: AsyncSession, *, embeddings: EmbeddingService | None = None
    ) -> None:
        self._session = session
        self._embeddings = embeddings or EmbeddingService()

    async def resolve_feature(self, text: str, project_id: uuid.UUID) -> list[FeatureCandidate]:
        specs = await self._session.execute(
            select(FeatureSpec, Feature)
            .join(Feature, FeatureSpec.feature_id == Feature.id)
            .where(FeatureSpec.project_id == project_id)
            .order_by(FeatureSpec.version.desc())
        )
        seen: set[uuid.UUID] = set()
        candidates: list[FeatureCandidate] = []
        tokens = text.lower().split()
        for spec, feat in specs.all():
            if feat.id in seen:
                continue
            seen.add(feat.id)
            hay = f"{feat.name} {feat.description} {spec.body}".lower()
            score = sum(1 for t in tokens if t in hay) / max(len(tokens), 1)
            if score > 0:
                candidates.append(
                    FeatureCandidate(
                        feature_id=feat.id,
                        feature_key=feat.key,
                        spec_id=spec.id,
                        spec_lineage_key=spec.lineage_key,
                        score=score,
                        retrieval_source="LEXICAL",
                    )
                )
        if candidates:
            return sorted(candidates, key=lambda c: c.score, reverse=True)[:10]

        vec = await self._embeddings.embed_texts(
            self._session,
            subject_type="FEATURE_QUERY",
            subject_key=sha256_hex({"q": text}),
            content_hash=sha256_hex({"q": text}),
            texts=[text],
            repository_id=None,
        )
        if not vec:
            return []
        # Semantic fallback against feature spec bodies stored as pseudo-entities is skipped;
        # return lexical-empty with SEMANTIC label when embedding matched nothing in index.
        return []

    async def search(
        self,
        q: str,
        index_version_id: uuid.UUID,
        modes: tuple[str, ...] = ("STRUCTURAL", "LEXICAL", "SEMANTIC"),
    ) -> list[RetrievalHit]:
        hits: list[RetrievalHit] = []
        seen: set[str] = set()
        if "LEXICAL" in modes:
            for hit in await LexicalRetrieval(self._session).search(index_version_id, q, "symbol"):
                if hit.stable_key not in seen:
                    seen.add(hit.stable_key)
                    hits.append(hit)
        if "STRUCTURAL" in modes and hits:
            first = hits[0]
            for n in await StructuralRetrieval(self._session).neighbors(first.entity_id, depth=1):
                if n.stable_key not in seen:
                    seen.add(n.stable_key)
                    hits.append(n)
        if "SEMANTIC" in modes:
            vec = await self._embeddings.embed_texts(
                self._session,
                subject_type="SEARCH_QUERY",
                subject_key=sha256_hex({"q": q}),
                content_hash=sha256_hex({"q": q}),
                texts=[q],
                repository_id=None,
            )
            if vec and vec[0]:
                for hit in await SemanticRetrieval(self._session).search(index_version_id, vec[0]):
                    if hit.stable_key not in seen:
                        seen.add(hit.stable_key)
                        hits.append(hit)
        return hits
