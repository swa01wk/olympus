from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPkMixin


class ChangeRequest(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "change_requests"
    __table_args__ = (UniqueConstraint("project_id", "source_type", "external_ref"),)

    key: Mapped[str] = mapped_column(String(16))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    delivery_cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("delivery_cycles.id"), default=None, index=True
    )
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(64))
    external_ref: Mapped[str | None] = mapped_column(String(256), default=None)
    inbound_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inbound_events.id"), default=None
    )
    product_source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product_sources.id"))
    status: Mapped[str] = mapped_column(String(32))
    resolved_feature_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("features.id"), default=None
    )
    spec_delta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("spec_deltas.id"), default=None
    )
    release_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("releases.id"), default=None)
    interpretation: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    interpretation_execution_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    candidate_features: Mapped[list[Any] | None] = mapped_column(JSONB, default=None)
