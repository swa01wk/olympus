from __future__ import annotations

import uuid

from core.commands.bus import CommandBus
from core.commands.context import CommandContext
from core.execution.artifacts import ArtifactStore
from core.integrations.inbound.service import InboundService
from core.product_model.sources.service import ProductSourceService
from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.command_dispatch import dispatch
from apps.control_api.deps import command_context, get_command_bus, get_db

router = APIRouter(tags=["sources"])


class JsonSourceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    text: str
    lineage_key: str = "default"
    source_type: str = "PRD"


class SourceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    version: int
    title: str
    lineage_key: str
    content_hash: str


@router.post("/projects/{project_id}/sources")
async def upload_source(
    request: Request,
    project_id: uuid.UUID,
    delivery_cycle_id: uuid.UUID | None = None,
    file: UploadFile | None = File(default=None),
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
    bus: CommandBus = Depends(get_command_bus),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, object]:
    if idempotency_key:
        ctx = CommandContext(
            actor=ctx.actor,
            correlation_id=ctx.correlation_id,
            idempotency_key=idempotency_key,
            command_log_id=ctx.command_log_id,
        )
    raw: dict[str, object] = {
        "project_id": str(project_id),
        "source_id": str(project_id),
        "event_id": idempotency_key or str(uuid.uuid4()),
        "delivery_cycle_id": str(delivery_cycle_id) if delivery_cycle_id else None,
    }
    if file is not None:
        raw["file_bytes"] = await file.read()
        raw["filename"] = file.filename or "upload.md"
        raw["mime_type"] = file.content_type or "text/plain"
    else:
        payload = JsonSourceBody.model_validate(await request.json())
        raw["json_body"] = payload.model_dump()
        raw["lineage_key"] = payload.lineage_key
        raw["source_type_label"] = payload.source_type
    return await InboundService(bus).receive(session, "document_upload", raw, ctx)


@router.get("/projects/{project_id}/sources", response_model=list[SourceResponse])
async def list_sources(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[SourceResponse]:
    rows = await ProductSourceService().list_for_project(session, project_id)
    return [
        SourceResponse(
            id=r.id,
            version=r.version,
            title=r.title,
            lineage_key=r.lineage_key,
            content_hash=r.content_hash,
        )
        for r in rows
    ]


@router.get("/projects/{project_id}/sources/{source_id}", response_model=SourceResponse)
async def get_source(
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> SourceResponse:
    row = await ProductSourceService().get(session, source_id)
    if row is None or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="Not found")
    return SourceResponse(
        id=row.id,
        version=row.version,
        title=row.title,
        lineage_key=row.lineage_key,
        content_hash=row.content_hash,
    )


@router.get("/projects/{project_id}/sources/{source_id}/content")
async def source_content(
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    row = await ProductSourceService().get(session, source_id)
    if row is None or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="Not found")
    from core.domain.artifacts.models import Artifact

    artifact = await session.get(Artifact, row.text_artifact_id)
    store = ArtifactStore()
    text = ""
    if artifact and artifact.inline and isinstance(artifact.inline, dict):
        text = str(artifact.inline.get("text", ""))
    elif artifact:
        import json

        text = str(json.loads(store.read_bytes(artifact).decode("utf-8")).get("text", ""))
    return {"title": row.title, "text": text, "mime_type": row.mime_type}


@router.post("/sources/{source_id}/decompose")
@router.post("/sources/{source_id}/derive")
async def decompose_source(
    source_id: uuid.UUID,
    payload: dict[str, str],
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
    bus: CommandBus = Depends(get_command_bus),
) -> dict[str, object]:
    result = await dispatch(
        session,
        bus,
        name="decompose_source",
        target_type="product_source",
        target_id=str(source_id),
        payload={
            "source_version_id": str(source_id),
            "delivery_cycle_id": payload["delivery_cycle_id"],
        },
        ctx=ctx,
    )
    return result.data
