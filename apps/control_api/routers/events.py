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
    event_type: str | None = Query(default=None),
    latest: bool = Query(default=False, description="Return the newest `limit` events"),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    from sqlalchemy import select

    query = select(DomainEvent).where(
        DomainEvent.delivery_cycle_id == cycle_id,
        DomainEvent.sequence > after_sequence,
    )
    if event_type:
        query = query.where(DomainEvent.event_type == event_type)
    order = DomainEvent.sequence.desc() if latest else DomainEvent.sequence
    rows = list((await session.execute(query.order_by(order).limit(limit))).scalars())
    if latest:
        rows.reverse()
    return [
        {
            "id": str(e.id),
            "sequence": e.sequence,
            "event_type": e.event_type,
            "payload": e.payload,
            "occurred_at": e.occurred_at.isoformat(),
        }
        for e in rows
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
