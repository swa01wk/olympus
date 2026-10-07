from __future__ import annotations

import uuid

from core.db.base import Base, TimestampMixin, UUIDPkMixin
from core.domain.enums import ProjectReadiness
from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class Project(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "projects"

    key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(String(4096), default=None)
    readiness_state: Mapped[ProjectReadiness] = mapped_column(default=ProjectReadiness.UNKNOWN)
    active_baseline_set_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("baseline_sets.id"), default=None
    )


class ProjectSequence(Base):
    __tablename__ = "project_sequences"
    __table_args__ = (UniqueConstraint("project_id", "sequence_name"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    sequence_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer, default=1)
