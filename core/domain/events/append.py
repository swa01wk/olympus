from __future__ import annotations

import uuid
from typing import Any

from core.domain.events.models import DomainEvent
from sqlalchemy.ext.asyncio import AsyncSession


async def append_domain_event(
    session: AsyncSession,
    *,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
    actor_id: uuid.UUID,
    correlation_id: str,
    project_id: uuid.UUID | None = None,
    delivery_cycle_id: uuid.UUID | None = None,
    causation_id: str | None = None,
    trace_context: dict[str, Any] | None = None,
) -> DomainEvent:
    if trace_context is None:
        from core.observability.otel import inject_trace_context

        trace_context = inject_trace_context()
    event = DomainEvent(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        payload=payload,
        actor_id=actor_id,
        correlation_id=correlation_id,
        project_id=project_id,
        delivery_cycle_id=delivery_cycle_id,
        causation_id=causation_id,
        trace_context=trace_context,
    )
    session.add(event)
    await session.flush()
    return event
