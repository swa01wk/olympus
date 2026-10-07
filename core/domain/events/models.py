from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import uuid6
from core.db.base import Base
from sqlalchemy import BigInteger, ForeignKey, Identity, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class DomainEvent(Base):
    __tablename__ = "domain_events"
    __table_args__ = (Index("ix_domain_events_delivery_cycle", "delivery_cycle_id", "sequence"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid6.uuid7)
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    aggregate_type: Mapped[str] = mapped_column(String(64))
    aggregate_id: Mapped[uuid.UUID]
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"), default=None)
    delivery_cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("delivery_cycles.id"), default=None
    )
    event_type: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    correlation_id: Mapped[str] = mapped_column(String(128))
    causation_id: Mapped[str | None] = mapped_column(String(128), default=None)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("actors.id"))
    occurred_at: Mapped[datetime] = mapped_column(server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(default=None)
    trace_context: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
