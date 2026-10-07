from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPkMixin


class Artifact(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "artifacts"

    key: Mapped[str] = mapped_column(String(64))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    delivery_cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("delivery_cycles.id"), default=None, index=True
    )
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("executions.id"), default=None, index=True
    )
    kind: Mapped[str] = mapped_column(String(128), index=True)
    schema_name: Mapped[str] = mapped_column(String(128))
    schema_version: Mapped[str] = mapped_column(String(32))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_ref: Mapped[str] = mapped_column(String(512))
    inline: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    created_by_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("actors.id"), default=None
    )

    __table_args__ = (UniqueConstraint("content_hash", "execution_id", "kind"),)
