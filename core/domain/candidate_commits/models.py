from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from core.db.base import Base, UUIDPkMixin
from sqlalchemy import ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class CandidateCommit(Base, UUIDPkMixin):
    __tablename__ = "candidate_commits"

    key: Mapped[str] = mapped_column(String(64))
    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("executions.id"), unique=True, index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"))
    repository_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repositories.id"))
    branch: Mapped[str] = mapped_column(String(256))
    sha: Mapped[str] = mapped_column(String(64))
    parent_sha: Mapped[str] = mapped_column(String(64))
    base_sha: Mapped[str] = mapped_column(String(64))
    changed_files: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    diff_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id"), default=None
    )
    principal_symbols_declared: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (UniqueConstraint("repository_id", "sha"),)
