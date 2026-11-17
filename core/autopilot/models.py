"""Per-cycle Autopilot switch and last reported status."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base


class AutopilotState(Base):
    """One row per delivery cycle that has Autopilot turned on (or once had it on).

    ``status`` is what the person sees: WORKING (agents or the system are busy),
    NEEDS_YOU (an approval, question or input is waiting), BLOCKED (something failed and
    Autopilot will not retry on its own), DONE (the cycle reached a terminal state).
    """

    __tablename__ = "autopilot_states"

    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_cycles.id"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(default=True)
    status: Mapped[str] = mapped_column(String(16), default="WORKING")
    step: Mapped[str] = mapped_column(String(64), default="starting")
    message: Mapped[str] = mapped_column(Text, default="Starting")
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Step code whose action raised; Autopilot will not run it again until retry is requested.
    failed_step: Mapped[str | None] = mapped_column(String(64), default=None)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    # Step code the person asked to retry (consumed on the next tick that reaches it).
    retry_step: Mapped[str | None] = mapped_column(String(64), default=None)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
