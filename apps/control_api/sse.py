from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

from core.domain.events.models import DomainEvent
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.responses import StreamingResponse


async def stream_delivery_cycle_events(
    session_factory: async_sessionmaker[AsyncSession],
    cycle_id: uuid.UUID,
    request: Request | None = None,
) -> StreamingResponse:
    last_id = 0
    if request is not None:
        header = request.headers.get("Last-Event-ID")
        if header and header.isdigit():
            last_id = int(header)

    async def generator() -> AsyncIterator[str]:
        nonlocal last_id
        yield ": connected\n\n"
        while True:
            async with session_factory() as session:
                result = await session.execute(
                    select(DomainEvent)
                    .where(
                        DomainEvent.delivery_cycle_id == cycle_id,
                        DomainEvent.sequence > last_id,
                    )
                    .order_by(DomainEvent.sequence)
                    .limit(20)
                )
                events = list(result.scalars())
            if not events:
                await asyncio.sleep(0.2)
                continue
            for event in events:
                last_id = event.sequence
                payload = json.dumps(
                    {
                        "id": str(event.id),
                        "sequence": event.sequence,
                        "event_type": event.event_type,
                        "payload": event.payload,
                    }
                )
                yield f"id: {event.sequence}\nevent: {event.event_type}\ndata: {payload}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")


async def stream_global_events(
    session_factory: async_sessionmaker[AsyncSession],
    request: Request | None = None,
    *,
    project_id: uuid.UUID | None = None,
) -> StreamingResponse:
    last_id = 0
    if request is not None:
        after = request.query_params.get("after")
        if after and after.isdigit():
            last_id = int(after)
        header = request.headers.get("Last-Event-ID")
        if header and header.isdigit():
            last_id = max(last_id, int(header))

    async def generator() -> AsyncIterator[str]:
        nonlocal last_id
        yield ": connected\n\n"
        while True:
            async with session_factory() as session:
                stmt = select(DomainEvent).where(DomainEvent.sequence > last_id)
                if project_id is not None:
                    stmt = stmt.where(DomainEvent.project_id == project_id)
                result = await session.execute(stmt.order_by(DomainEvent.sequence).limit(20))
                events = list(result.scalars())
            if not events:
                await asyncio.sleep(0.2)
                continue
            for event in events:
                last_id = event.sequence
                payload = json.dumps(
                    {
                        "id": str(event.id),
                        "sequence": event.sequence,
                        "event_type": event.event_type,
                        "payload": event.payload,
                        "delivery_cycle_id": str(event.delivery_cycle_id)
                        if event.delivery_cycle_id
                        else None,
                        "project_id": str(event.project_id) if event.project_id else None,
                    }
                )
                yield f"id: {event.sequence}\nevent: message\ndata: {payload}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")
