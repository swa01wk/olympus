from __future__ import annotations

import uuid

from core.domain.artifacts.models import Artifact
from core.execution.artifacts import ArtifactStore
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import get_db

router = APIRouter(tags=["artifacts"])


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    key: str
    kind: str
    content_hash: str
    size_bytes: int
    execution_id: uuid.UUID | None


@router.get("/executions/{execution_id}/artifacts", response_model=list[ArtifactResponse])
async def list_execution_artifacts(
    execution_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[ArtifactResponse]:
    from sqlalchemy import select

    result = await session.execute(select(Artifact).where(Artifact.execution_id == execution_id))
    return [
        ArtifactResponse(
            id=a.id,
            key=a.key,
            kind=a.kind,
            content_hash=a.content_hash,
            size_bytes=a.size_bytes,
            execution_id=a.execution_id,
        )
        for a in result.scalars()
    ]


@router.get("/artifacts/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(
    artifact_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ArtifactResponse:
    row = await session.get(Artifact, artifact_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return ArtifactResponse(
        id=row.id,
        key=row.key,
        kind=row.kind,
        content_hash=row.content_hash,
        size_bytes=row.size_bytes,
        execution_id=row.execution_id,
    )


@router.get("/artifacts/{artifact_id}/content")
async def artifact_content(
    artifact_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    row = await session.get(Artifact, artifact_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    if row.inline is not None:
        return {"inline": row.inline}
    store = ArtifactStore()
    raw = store.read_bytes(row)
    return {"bytes": raw.decode("utf-8", errors="replace")}
