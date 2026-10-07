from __future__ import annotations

import uuid
from typing import Any

from core.commands.context import CommandContext
from core.domain.exceptions import DomainError
from core.domain.repositories.models import Repository
from core.intelligence.code_index.enums import EntityType, IndexKind, IndexSource, RelationType
from core.intelligence.code_index.indexer import CodeIndexer
from core.intelligence.code_index.models import CodeEntity, CodeIndexVersion, CodeRelation
from core.intelligence.code_index.retrieval.lexical import LexicalRetrieval
from core.intelligence.code_index.retrieval.structural import StructuralRetrieval
from core.intelligence.code_index.retrieval.types import RetrievalHit
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import command_context, get_db

router = APIRouter(tags=["code-intelligence"])


class RebuildCodeIndexRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository_id: uuid.UUID
    sha: str | None = None
    kind: IndexKind = IndexKind.CANDIDATE


class CodeIndexVersionResponse(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    commit_sha: str
    kind: str
    source: str
    scope_ref: str
    status: str
    indexer_version: str
    content_hash: str | None
    stats: dict[str, Any]


class EntityResponse(BaseModel):
    id: uuid.UUID
    stable_key: str
    type: str
    qualified_name: str
    file_path: str | None
    start_line: int | None
    end_line: int | None
    content_hash: str | None
    is_public: bool
    metadata: dict[str, Any]


class RelationBrief(BaseModel):
    id: uuid.UUID
    relation: str
    direction: str
    entity: EntityResponse
    provenance: str
    confidence: float


def _entity_response(row: CodeEntity) -> EntityResponse:
    return EntityResponse(
        id=row.id,
        stable_key=row.stable_key,
        type=row.type.value,
        qualified_name=row.qualified_name,
        file_path=row.file_path,
        start_line=row.start_line,
        end_line=row.end_line,
        content_hash=row.content_hash,
        is_public=row.is_public,
        metadata=row.entity_metadata,
    )


def _version_response(row: CodeIndexVersion) -> CodeIndexVersionResponse:
    return CodeIndexVersionResponse(
        id=row.id,
        repository_id=row.repository_id,
        commit_sha=row.commit_sha,
        kind=row.kind.value,
        source=row.source.value,
        scope_ref=row.scope_ref,
        status=row.status.value,
        indexer_version=row.indexer_version,
        content_hash=row.content_hash,
        stats=row.stats,
    )


@router.post("/projects/{project_id}/code-index/rebuild")
async def rebuild_code_index(
    project_id: uuid.UUID,
    body: RebuildCodeIndexRequest,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> CodeIndexVersionResponse:
    if body.kind == IndexKind.CANONICAL:
        raise HTTPException(status_code=422, detail={"code": "CANONICAL_INDEX_RESERVED"})
    repo = await session.get(Repository, body.repository_id)
    if repo is None or repo.project_id != project_id:
        raise HTTPException(status_code=404, detail="Repository not found")
    sha = body.sha or repo.canonical_commit
    if not sha:
        raise HTTPException(status_code=422, detail={"code": "REPOSITORY_NOT_READY"})
    try:
        version = await CodeIndexer().build(
            session,
            body.repository_id,
            sha,
            body.kind,
            IndexSource.REPOSITORY_SNAPSHOT,
            ctx,
        )
    except DomainError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    return _version_response(version)


@router.get("/repositories/{repository_id}/code-index/versions")
async def list_code_index_versions(
    repository_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[CodeIndexVersionResponse]:
    rows = (
        (
            await session.execute(
                select(CodeIndexVersion)
                .where(CodeIndexVersion.repository_id == repository_id)
                .order_by(CodeIndexVersion.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_version_response(r) for r in rows]


@router.get("/code-index/versions/{version_id}")
async def get_code_index_version(
    version_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> CodeIndexVersionResponse:
    row = await session.get(CodeIndexVersion, version_id)
    if row is None:
        raise HTTPException(status_code=404)
    return _version_response(row)


@router.get("/code/entities")
async def list_entities(
    session: AsyncSession = Depends(get_db),
    index_version_id: uuid.UUID = Query(...),
    type: EntityType | None = Query(None),
    file: str | None = Query(None),
    q: str | None = Query(None),
) -> list[EntityResponse]:
    stmt = select(CodeEntity).where(CodeEntity.index_version_id == index_version_id)
    if type is not None:
        stmt = stmt.where(CodeEntity.type == type)
    if file:
        stmt = stmt.where(CodeEntity.file_path == file)
    if q:
        stmt = stmt.where(CodeEntity.qualified_name.ilike(f"%{q}%"))
    rows = (await session.execute(stmt)).scalars().all()
    return [_entity_response(r) for r in rows]


@router.get("/code/entities/{entity_id}")
async def get_entity(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = await session.get(CodeEntity, entity_id)
    if row is None:
        raise HTTPException(status_code=404)
    out_rel = (
        await session.execute(
            select(CodeRelation, CodeEntity)
            .join(CodeEntity, CodeRelation.target_entity_id == CodeEntity.id)
            .where(CodeRelation.source_entity_id == entity_id)
        )
    ).all()
    in_rel = (
        await session.execute(
            select(CodeRelation, CodeEntity)
            .join(CodeEntity, CodeRelation.source_entity_id == CodeEntity.id)
            .where(CodeRelation.target_entity_id == entity_id)
        )
    ).all()
    return {
        "entity": _entity_response(row),
        "relations_out": [
            RelationBrief(
                id=rel.id,
                relation=rel.relation.value,
                direction="out",
                entity=_entity_response(ent),
                provenance=rel.provenance,
                confidence=rel.confidence,
            )
            for rel, ent in out_rel
        ],
        "relations_in": [
            RelationBrief(
                id=rel.id,
                relation=rel.relation.value,
                direction="in",
                entity=_entity_response(ent),
                provenance=rel.provenance,
                confidence=rel.confidence,
            )
            for rel, ent in in_rel
        ],
    }


@router.get("/code/entities/{entity_id}/neighbors")
async def entity_neighbors(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    relation: list[RelationType] | None = Query(None),
    direction: str = Query("both"),
    depth: int = Query(1, ge=1, le=4),
) -> list[RetrievalHit]:
    rel_set = set(relation) if relation else None
    return await StructuralRetrieval(session).neighbors(entity_id, rel_set, direction, depth)


@router.get("/code/search")
async def code_search(
    session: AsyncSession = Depends(get_db),
    q: str = Query(...),
    mode: str = Query("symbol"),
    index_version_id: uuid.UUID = Query(...),
) -> list[RetrievalHit]:
    if mode == "hybrid":
        from core.intelligence.code_index.retrieval.hybrid import HybridRetrieval

        return await HybridRetrieval(session).search(q, index_version_id)
    return await LexicalRetrieval(session).search(index_version_id, q, mode)


@router.get("/code/paths")
async def code_paths(
    session: AsyncSession = Depends(get_db),
    from_id: uuid.UUID = Query(..., alias="from"),
    to_id: uuid.UUID = Query(..., alias="to"),
    relations: list[RelationType] | None = Query(None),
) -> dict[str, Any]:
    rel_set = set(relations) if relations else None
    path = await StructuralRetrieval(session).path(from_id, to_id, rel_set)
    if path is None:
        return {"path": None}
    return {"path": path}


@router.get("/repositories/{repository_id}/code-index/canonical/refresh-report")
async def latest_refresh_report(
    repository_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    from core.domain.artifacts.models import Artifact

    repo = await session.get(Repository, repository_id)
    if repo is None:
        raise HTTPException(404, "Repository not found")
    row = (
        await session.execute(
            select(Artifact)
            .where(
                Artifact.project_id == repo.project_id,
                Artifact.kind == "spec_code_link.refresh_report",
            )
            .order_by(Artifact.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        return {"report": None}
    return {
        "artifact_id": str(row.id),
        "content_hash": row.content_hash,
        "report": row.inline or {},
    }
