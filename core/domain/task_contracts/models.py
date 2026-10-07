from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from core.db.base import Base, TimestampMixin, UUIDPkMixin
from core.domain.enums import TaskContractStatus
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class TaskContract(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "task_contracts"
    __table_args__ = (UniqueConstraint("task_id", "version"),)

    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    version: Mapped[int]
    status: Mapped[TaskContractStatus]
    body: Mapped[dict[str, Any]] = mapped_column(JSONB)
    content_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    compiled_by: Mapped[str] = mapped_column(String(128))
    compiler_inputs_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    issued_at: Mapped[datetime | None] = mapped_column(default=None)
