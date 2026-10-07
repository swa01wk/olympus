from __future__ import annotations

import uuid

from core.commands.bus import CommandBus
from core.commands.context import CommandContext
from core.integrations.inbound.models import InboundEvent
from core.integrations.inbound.service import InboundService
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import command_context, get_command_bus, get_db

router = APIRouter(prefix="/integrations", tags=["inbound"])


@router.post("/events/{provider}")
async def provider_events_alias(
    provider: str,
    payload: dict[str, object],
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
    bus: CommandBus = Depends(get_command_bus),
) -> dict[str, object]:
    source = f"{provider}_webhook" if not provider.endswith("_webhook") else provider
    if provider in {"github", "gitea"}:
        source = "git_provider_webhook"
        payload = {**payload, "source_id": provider}
    return await InboundService(bus).receive(session, source, payload, ctx)


@router.post("/inbound/{source}")
async def generic_inbound(
    source: str,
    payload: dict[str, object],
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
    bus: CommandBus = Depends(get_command_bus),
) -> dict[str, object]:
    adapter = "document_upload" if source == "document_upload" else source
    return await InboundService(bus).receive(session, adapter, payload, ctx)


class InboundEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    source_type: str
    status: str
    event_id: str


@router.get("/inbound-events", response_model=list[InboundEventResponse])
async def list_inbound_events(
    session: AsyncSession = Depends(get_db),
) -> list[InboundEventResponse]:
    rows = await session.execute(select(InboundEvent).order_by(InboundEvent.created_at.desc()))
    return [
        InboundEventResponse(
            id=r.id,
            source_type=r.source_type,
            status=r.status.value,
            event_id=r.event_id,
        )
        for r in rows.scalars()
    ]


@router.get("/inbound-events/{event_id}", response_model=InboundEventResponse)
async def get_inbound_event(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> InboundEventResponse:
    row = await session.get(InboundEvent, event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return InboundEventResponse(
        id=row.id,
        source_type=row.source_type,
        status=row.status.value,
        event_id=row.event_id,
    )
