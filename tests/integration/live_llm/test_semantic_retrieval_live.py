from __future__ import annotations

import os

import pytest
from core.config.settings import get_settings
from core.intelligence.code_index.embeddings import EmbeddingService
from core.intelligence.code_index.enums import IndexKind, IndexSource
from core.intelligence.code_index.indexer import CodeIndexer
from core.intelligence.code_index.models import CodeEntity
from core.intelligence.code_index.retrieval.hybrid import HybridRetrieval
from core.runtime.contracts import EmbeddingRequest
from core.runtime.errors import ProviderAuthError, ProviderTransientError
from core.runtime.model_router import ModelRouter, build_providers
from sqlalchemy import select
from tests.fixtures.code_index_harness import materialize_supportdesk_r1
from tests.live_credentials import configured_embedding_model, openai_embedding_configured

pytestmark = [pytest.mark.live_llm, pytest.mark.integration, pytest.mark.asyncio]


async def _probe_embedding_router(router: ModelRouter) -> None:
    model = configured_embedding_model()
    try:
        result = await router.embed(
            EmbeddingRequest(
                alias="embedding",
                texts=["olympus embedding probe"],
                metadata={"purpose": "live_semantic_probe"},
            )
        )
    except ProviderAuthError as exc:
        pytest.skip(f"OpenAI embedding auth failed for {model}: {exc}")
    except ProviderTransientError as exc:
        msg = str(exc).lower()
        if "not allowed" in msg or "403" in msg:
            pytest.skip(
                f"OpenAI key lacks embedding entitlement for MODEL_EMBEDDING={model!r}; "
                "use a permitted model or a key/project allowed for MODEL_EMBEDDING"
            )
        pytest.skip(f"Live embedding provider unavailable for {model}: {exc}")
    except Exception as exc:
        pytest.skip(f"Live embedding probe failed for {model}: {type(exc).__name__}: {exc}")
    if not result.vectors or not result.vectors[0]:
        pytest.skip(f"Live embedding returned no vectors for {model}")


@pytest.mark.skipif(not os.getenv("LLM_LIVE_TESTS"), reason="LLM_LIVE_TESTS not set")
async def test_semantic_retrieval_supportdesk_case(db_session, system_ctx, system_actor) -> None:
    if not openai_embedding_configured():
        pytest.skip(
            "OpenAI API key and MODEL_EMBEDDING required for embedding alias "
            f"(current MODEL_EMBEDDING={get_settings().model_embedding!r})"
        )

    router = ModelRouter(
        db_session,
        actor_id=system_actor.id,
        providers=build_providers(),
    )
    await _probe_embedding_router(router)

    repo, sha = await materialize_supportdesk_r1(db_session, system_ctx)
    version = await CodeIndexer().build(
        db_session,
        repo.id,
        sha,
        IndexKind.CANDIDATE,
        IndexSource.REPOSITORY_SNAPSHOT,
        system_ctx,
        scope_ref="live-semantic",
    )
    embed = EmbeddingService(router)
    entities = (
        await db_session.execute(
            select(CodeEntity)
            .where(CodeEntity.index_version_id == version.id)
            .order_by(CodeEntity.stable_key)
            .limit(48)
        )
    ).scalars()
    embedded = 0
    for ent in entities:
        vec = await embed.entity_vector(db_session, ent, None, repo.id)
        if vec:
            embedded += 1
    assert embedded > 0, (
        f"expected CODE_ENTITY embeddings after successful probe "
        f"(MODEL_EMBEDDING={configured_embedding_model()!r})"
    )

    hybrid = HybridRetrieval(db_session, embeddings=embed)
    hits = await hybrid.search(
        "close a support case",
        version.id,
        modes=("SEMANTIC", "LEXICAL"),
    )
    semantic = [h for h in hits if h.retrieval_source == "SEMANTIC"]
    assert semantic, "expected semantic hits after indexing entity vectors"
    assert semantic[0].score > 0
