from __future__ import annotations

import uuid
from datetime import datetime

from core.db.base import Base, TimestampMixin, UUIDPkMixin
from core.domain.enums import ApprovalStatus, ApprovalType
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class Approval(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "approvals"
    __table_args__ = (UniqueConstraint("project_id", "key"),)

    key: Mapped[str] = mapped_column(String(64))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    delivery_cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("delivery_cycles.id"), default=None
    )
    approval_type: Mapped[ApprovalType]
    subject_type: Mapped[str] = mapped_column(String(64))
    subject_id: Mapped[uuid.UUID]
    subject_version: Mapped[int]
    subject_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[ApprovalStatus] = mapped_column(default=ApprovalStatus.PENDING)
    requested_by_actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("actors.id"))
    decided_by_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("actors.id"), default=None
    )
    decision_note: Mapped[str | None] = mapped_column(String(4096), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(default=None)
    policy_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("policy_versions.id"), default=None
    )
