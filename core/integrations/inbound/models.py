from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPkMixin
from core.domain.enums import InboundEventStatus, IntegrationAuthKind


class IntegrationSource(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "integration_sources"

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id"), index=True, default=None
    )
    source_type: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(256))
    auth_kind: Mapped[IntegrationAuthKind]
    secret_ref: Mapped[str | None] = mapped_column(String(256), default=None)
    secondary_secret_ref: Mapped[str | None] = mapped_column(String(256), default=None)
    secondary_valid_until: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    active: Mapped[bool] = mapped_column(default=True)


class InboundEvent(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "inbound_events"
    __table_args__ = (UniqueConstraint("source_type", "source_id", "event_id"),)

    source_type: Mapped[str] = mapped_column(String(64), index=True)
    source_id: Mapped[str] = mapped_column(String(256))
    event_id: Mapped[str] = mapped_column(String(256))
    status: Mapped[InboundEventStatus] = mapped_column(index=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, default=None)
    payload_storage_ref: Mapped[str | None] = mapped_column(String(512), default=None)
    payload_inline: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    normalized: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    command_log_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("command_log.id"), default=None
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("actors.id"), default=None)
    correlation_id: Mapped[str | None] = mapped_column(String(128), default=None)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id"), index=True, default=None
    )
