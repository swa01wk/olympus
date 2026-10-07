from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from core.db.base import Base, TimestampMixin, UUIDPkMixin
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class OrchestratorSession(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "orchestrator_sessions"

    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("actors.id"), index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"), default=None)
    delivery_cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("delivery_cycles.id"), default=None
    )
    turns: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    expires_at: Mapped[datetime]
