from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import uuid6
from core.db.base import Base
from core.domain.enums import ActorKind
from sqlalchemy import BigInteger, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid6.uuid7)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("actors.id"))
    actor_kind: Mapped[ActorKind]
    action: Mapped[str] = mapped_column(String(128))
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(64))
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    correlation_id: Mapped[str] = mapped_column(String(128))
    command_log_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id"), default=None, index=True
    )
    prev_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    hash: Mapped[str] = mapped_column(String(64))
    chain_seq: Mapped[int] = mapped_column(BigInteger)
    occurred_at: Mapped[datetime] = mapped_column(server_default=func.now())
