from __future__ import annotations

import uuid
from datetime import datetime

from core.db.base import Base, TimestampMixin, UUIDPkMixin
from core.domain.enums import DeliveryCycleType
from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class DeliveryCycle(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "delivery_cycles"
    __table_args__ = (UniqueConstraint("project_id", "key"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    type: Mapped[DeliveryCycleType]
    objective: Mapped[str] = mapped_column(String(4096))
    state: Mapped[str] = mapped_column(String(64))
    state_version: Mapped[int] = mapped_column(Integer, default=0)
    repository_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("repositories.id"), default=None
    )
    base_sha: Mapped[str | None] = mapped_column(String(64), default=None)
    terminal_reason: Mapped[str | None] = mapped_column(String(1024), default=None)
    closed_at: Mapped[datetime | None] = mapped_column(default=None)
    opened_by_actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("actors.id"))
