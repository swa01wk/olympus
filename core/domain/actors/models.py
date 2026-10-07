from __future__ import annotations

import uuid
from datetime import datetime

from core.db.base import Base, TimestampMixin, UUIDPkMixin
from core.domain.enums import ActorKind
from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column


class Actor(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "actors"

    kind: Mapped[ActorKind]
    name: Mapped[str] = mapped_column(String(128), unique=True)
    roles: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ApiToken(Base, UUIDPkMixin):
    __tablename__ = "api_tokens"

    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("actors.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    rotated_from_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("api_tokens.id"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)
