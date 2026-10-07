from __future__ import annotations

import uuid
from datetime import datetime

from core.db.base import Base, UUIDPkMixin
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


class ExecutionToken(Base, UUIDPkMixin):
    __tablename__ = "execution_tokens"

    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executions.id"), index=True)
    lease_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("execution_leases.id"))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    worker_id: Mapped[str | None] = mapped_column(String(128), default=None)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)
