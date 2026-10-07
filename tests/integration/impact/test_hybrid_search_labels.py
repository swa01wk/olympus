from __future__ import annotations

import pytest
from core.intelligence.code_index.enums import IndexKind, IndexSource
from core.intelligence.code_index.indexer import CodeIndexer
from core.intelligence.code_index.retrieval.hybrid import HybridRetrieval
from tests.fixtures.code_index_harness import materialize_supportdesk_r1

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_hybrid_search_sources_distinct(db_session, system_ctx) -> None:
    repo, sha = await materialize_supportdesk_r1(db_session, system_ctx)
    version = await CodeIndexer().build(
        db_session,
        repo.id,
        sha,
        IndexKind.CANDIDATE,
        IndexSource.REPOSITORY_SNAPSHOT,
        system_ctx,
        scope_ref="hybrid-labels",
    )
    hits = await HybridRetrieval(db_session).search(
        "update_status",
        version.id,
        modes=("LEXICAL", "STRUCTURAL"),
    )
    sources = {h.retrieval_source for h in hits}
    assert "LEXICAL" in sources
