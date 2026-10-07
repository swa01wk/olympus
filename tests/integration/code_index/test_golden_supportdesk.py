from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from core.intelligence.code_index.enums import EntityType, IndexKind, IndexSource
from core.intelligence.code_index.indexer import CodeIndexer
from core.intelligence.code_index.models import CodeEntity, CodeRelation
from core.intelligence.code_index.retrieval.lexical import LexicalRetrieval
from core.intelligence.code_index.retrieval.structural import StructuralRetrieval
from sqlalchemy import select

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "repos"
EXPECTED_PATH = _FIXTURES / "supportdesk_r1.expected_index.json"


async def _relation_tuples(session, version_id):
    entities = (
        (await session.execute(select(CodeEntity).where(CodeEntity.index_version_id == version_id)))
        .scalars()
        .all()
    )
    id_to_key = {ent.id: ent.stable_key for ent in entities}
    rel_rows = (
        (
            await session.execute(
                select(CodeRelation).where(CodeRelation.index_version_id == version_id)
            )
        )
        .scalars()
        .all()
    )
    rels = [
        (id_to_key[r.source_entity_id], r.relation.value, id_to_key[r.target_entity_id])
        for r in rel_rows
        if r.source_entity_id in id_to_key and r.target_entity_id in id_to_key
    ]
    return sorted(rels)


async def test_regenerate_supportdesk_golden_index(
    db_session, system_ctx, supportdesk_repository
) -> None:
    if os.getenv("OLYMPUS_REGEN_GOLDEN") != "1":
        pytest.skip("set OLYMPUS_REGEN_GOLDEN=1 to rewrite supportdesk_r1.expected_index.json")
    repo, sha = supportdesk_repository
    version = await CodeIndexer().build(
        db_session,
        repo.id,
        sha,
        IndexKind.CANDIDATE,
        IndexSource.REPOSITORY_SNAPSHOT,
        system_ctx,
    )
    entities = (
        (
            await db_session.execute(
                select(CodeEntity).where(CodeEntity.index_version_id == version.id)
            )
        )
        .scalars()
        .all()
    )
    keys = sorted(e.stable_key for e in entities)
    rels = await _relation_tuples(db_session, version.id)
    payload = {"entities": keys, "relations": [list(r) for r in rels]}
    EXPECTED_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


async def test_supportdesk_golden_index(db_session, system_ctx, supportdesk_repository) -> None:
    repo, sha = supportdesk_repository
    version = await CodeIndexer().build(
        db_session,
        repo.id,
        sha,
        IndexKind.CANDIDATE,
        IndexSource.REPOSITORY_SNAPSHOT,
        system_ctx,
    )
    entities = (
        (
            await db_session.execute(
                select(CodeEntity).where(CodeEntity.index_version_id == version.id)
            )
        )
        .scalars()
        .all()
    )
    keys = sorted(e.stable_key for e in entities)
    rels = await _relation_tuples(db_session, version.id)

    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    assert keys == sorted(expected["entities"])
    assert rels == [tuple(r) for r in expected["relations"]]


async def test_deterministic_content_hash(db_session, system_ctx, supportdesk_repository) -> None:
    repo, sha = supportdesk_repository
    v1 = await CodeIndexer().build(
        db_session, repo.id, sha, IndexKind.CANDIDATE, IndexSource.REPOSITORY_SNAPSHOT, system_ctx
    )
    v2 = await CodeIndexer().build(
        db_session, repo.id, sha, IndexKind.CANDIDATE, IndexSource.REPOSITORY_SNAPSHOT, system_ctx
    )
    assert v1.id == v2.id
    assert v1.content_hash == v2.content_hash


async def test_route_chain_traversal(db_session, system_ctx, supportdesk_repository) -> None:
    repo, sha = supportdesk_repository
    version = await CodeIndexer().build(
        db_session, repo.id, sha, IndexKind.CANDIDATE, IndexSource.REPOSITORY_SNAPSHOT, system_ctx
    )
    route = (
        await db_session.execute(
            select(CodeEntity).where(
                CodeEntity.index_version_id == version.id,
                CodeEntity.stable_key == "ROUTE:POST /tickets",
            )
        )
    ).scalar_one()
    neighbors = await StructuralRetrieval(db_session).neighbors(
        route.id, relations=None, direction="both", depth=6
    )
    keys = {h.stable_key for h in neighbors}
    assert any("TicketService.create" in k for k in keys)
    assert any("TicketRepository.add" in k for k in keys)
    table = (
        (
            await db_session.execute(
                select(CodeEntity).where(
                    CodeEntity.index_version_id == version.id,
                    CodeEntity.type == EntityType.TABLE,
                )
            )
        )
        .scalars()
        .all()
    )
    assert any(t.stable_key == "TABLE:tickets" for t in table)


async def test_lexical_search_update_status(db_session, system_ctx, supportdesk_repository) -> None:
    repo, sha = supportdesk_repository
    version = await CodeIndexer().build(
        db_session, repo.id, sha, IndexKind.CANDIDATE, IndexSource.REPOSITORY_SNAPSHOT, system_ctx
    )
    hits = await LexicalRetrieval(db_session).search(version.id, "update_status", mode="symbol")
    assert hits
    assert hits[0].retrieval_source == "LEXICAL"
    assert "update_status" in hits[0].qualified_name
