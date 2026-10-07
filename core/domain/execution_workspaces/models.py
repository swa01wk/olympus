from __future__ import annotations

import uuid
from datetime import datetime

from core.db.base import Base, TimestampMixin, UUIDPkMixin
from core.domain.enums import (
    ExecutionWorkspaceMode,
    ExecutionWorkspaceState,
    ExecutionWorkspaceType,
)
from sqlalchemy import CheckConstraint, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column


class ExecutionWorkspace(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "execution_workspaces"

    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("executions.id"), unique=True, index=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repositories.id"), index=True)
    workspace_type: Mapped[ExecutionWorkspaceType] = mapped_column(
        default=ExecutionWorkspaceType.GIT_WORKTREE
    )
    mode: Mapped[ExecutionWorkspaceMode]
    base_commit: Mapped[str] = mapped_column(String(64))
    logical_location: Mapped[str] = mapped_column(String(512))
    branch: Mapped[str | None] = mapped_column(String(256), default=None)
    state: Mapped[ExecutionWorkspaceState] = mapped_column(default=ExecutionWorkspaceState.CREATING)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    removed_at: Mapped[datetime | None] = mapped_column(default=None)

    __table_args__ = (
        CheckConstraint(
            "logical_location !~ '(^/|^[A-Za-z]:|\\.\\.)'",
            name="ck_execution_workspaces_logical",
        ),
        Index(
            "uq_execution_workspaces_logical_active",
            "logical_location",
            unique=True,
            postgresql_where=text("state IN ('CREATING','ACTIVE','RETAINED')"),
        ),
    )
