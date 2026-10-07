from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from core.db.base import Base, UUIDPkMixin
from core.domain.enums import CommandLogStatus
from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class PolicyVersion(Base, UUIDPkMixin):
    __tablename__ = "policy_versions"
    __table_args__ = (UniqueConstraint("content_hash"),)

    name: Mapped[str] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class CommandLog(Base, UUIDPkMixin):
    __tablename__ = "command_log"
    __table_args__ = (UniqueConstraint("actor_id", "idempotency_key"),)

    command_name: Mapped[str] = mapped_column(String(128))
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("actors.id"))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[CommandLogStatus]
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    correlation_id: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
