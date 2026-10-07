from __future__ import annotations

import uuid

from core.domain.events.models import DomainEvent
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.responses import StreamingResponse

from apps.control_api.deps import get_db, get_session_factory
from apps.control_api.sse import stream_delivery_cycle_events, stream_global_events

router = APIRouter(tags=["events"])


@router.get("/delivery-cycles/{cycle_id}/events")
async def list_events(
    cycle_id: uuid.UUID,
    after_sequence: int = Query(default=0, alias="after_sequence"),
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    from sqlalchemy import select

    result = await session.execute(
        select(DomainEvent)
        .where(
            DomainEvent.delivery_cycle_id == cycle_id,
            DomainEvent.sequence > after_sequence,
        )
        .order_by(DomainEvent.sequence)
        .limit(limit)
    )
    return [
        {
            "id": str(e.id),
            "sequence": e.sequence,
            "event_type": e.event_type,
            "payload": e.payload,
            "occurred_at": e.occurred_at.isoformat(),
        }
        for e in result.scalars()
    ]


@router.get("/delivery-cycles/{cycle_id}/events/stream")
async def events_stream(
    cycle_id: uuid.UUID,
    request: Request,
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> StreamingResponse:
    return await stream_delivery_cycle_events(session_factory, cycle_id, request)


@router.get("/events/stream")
async def global_events_stream(
    request: Request,
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    project_id: uuid.UUID | None = Query(default=None),
) -> StreamingResponse:
    return await stream_global_events(session_factory, request, project_id=project_id)
