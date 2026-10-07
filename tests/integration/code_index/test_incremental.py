from __future__ import annotations

import pytest
from core.intelligence.code_index.enums import IndexKind, IndexSource
from core.intelligence.code_index.incremental import IncrementalIndexBuilder
from core.intelligence.code_index.indexer import CodeIndexer
from tests.fixtures.code_index_harness import materialize_supportdesk_r1

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_incremental_matches_full_build_hash(db_session, system_ctx) -> None:
    ctx = system_ctx
    repo, sha = await materialize_supportdesk_r1(db_session, ctx)
    indexer = CodeIndexer()
    parent = await indexer.build(
        db_session,
        repo.id,
        sha,
        IndexKind.CANDIDATE,
        IndexSource.REPOSITORY_SNAPSHOT,
        ctx,
        scope_ref="incremental-parent",
    )
    inc = await IncrementalIndexBuilder().build_incremental(
        db_session,
        repo.id,
        parent.id,
        sha,
        IndexKind.CANDIDATE,
        IndexSource.REPOSITORY_SNAPSHOT,
        ctx,
        scope_ref="incremental-child",
    )
    full = await indexer.build(
        db_session,
        repo.id,
        sha,
        IndexKind.CANDIDATE,
        IndexSource.REPOSITORY_SNAPSHOT,
        ctx,
        scope_ref="full-verify",
    )
    assert inc.content_hash == full.content_hash
