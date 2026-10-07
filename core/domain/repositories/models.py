from __future__ import annotations

import uuid
from datetime import datetime

from core.db.base import Base, TimestampMixin, UUIDPkMixin
from core.domain.enums import (
    RepositoryProvider,
    RepositorySourceType,
    RepositoryStatus,
    RevisionCause,
    WorkspaceState,
)
from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column


class Repository(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "repositories"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), unique=True)
    name: Mapped[str] = mapped_column(String(256))
    source_type: Mapped[RepositorySourceType]
    provider: Mapped[RepositoryProvider]
    remote_url: Mapped[str | None] = mapped_column(String(2048), default=None)
    default_branch: Mapped[str] = mapped_column(String(256), default="main")
    registered_sha: Mapped[str | None] = mapped_column(String(64), default=None)
    canonical_commit: Mapped[str | None] = mapped_column(String(64), default=None)
    released_commit: Mapped[str | None] = mapped_column(String(64), default=None)
    status: Mapped[RepositoryStatus]
    status_reason: Mapped[str | None] = mapped_column(String(1024), default=None)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("repository_workspaces.id", use_alter=True, name="fk_repositories_workspace_id"),
        default=None,
    )
    credential_ref: Mapped[str] = mapped_column(String(512), default="none:")
    last_known_head_sha: Mapped[str | None] = mapped_column(String(64), default=None)
    webhook_external_id: Mapped[str | None] = mapped_column(String(256), default=None)
    last_synced_at: Mapped[datetime | None] = mapped_column(default=None)
    state_version: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        CheckConstraint(
            "credential_ref ~ '^(none|env|file|secret):[A-Za-z0-9_./-]*$'",
            name="ck_repositories_credential_ref",
        ),
        CheckConstraint(
            "remote_url IS NULL OR remote_url !~ '^[a-z+]+://[^/@]*@'",
            name="ck_repositories_remote_url_no_userinfo",
        ),
        CheckConstraint(
            "status <> 'READY' OR canonical_commit IS NOT NULL",
            name="ck_repositories_ready_has_commit",
        ),
    )


class RepositoryWorkspace(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "repository_workspaces"

    repository_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repositories.id"), index=True)
    workspace_type: Mapped[str] = mapped_column(String(32), default="CANONICAL")
    storage_backend: Mapped[str] = mapped_column(String(64), default="LOCAL_FILESYSTEM")
    logical_location: Mapped[str] = mapped_column(String(512))
    materialized_commit: Mapped[str | None] = mapped_column(String(64), default=None)
    state: Mapped[WorkspaceState] = mapped_column(default=WorkspaceState.PENDING)

    __table_args__ = (
        UniqueConstraint("repository_id", "workspace_type"),
        UniqueConstraint("storage_backend", "logical_location"),
        CheckConstraint(
            "logical_location !~ '(^/|^[A-Za-z]:|\\.\\.)'",
            name="ck_repository_workspaces_logical",
        ),
    )


class RepositoryRevision(Base, UUIDPkMixin):
    __tablename__ = "repository_revisions"

    repository_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repositories.id"), index=True)
    sequence: Mapped[int]
    commit_sha: Mapped[str] = mapped_column(String(64))
    cause: Mapped[RevisionCause]
    integration_candidate_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    release_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    repository_event_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    reverts_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("repository_revisions.id"), default=None
    )
    canonical_index_version_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    delivery_cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("delivery_cycles.id"), default=None
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("actors.id"))
    correlation_id: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (UniqueConstraint("repository_id", "sequence"),)
