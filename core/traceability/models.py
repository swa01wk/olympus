from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Float, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPkMixin
from core.integration.enums import (
    EntityChangeKind,
    SpecCodeLinkOrigin,
    SpecCodeLinkRelation,
    SpecCodeLinkStatus,
)


class RepositoryIndexPointer(Base):
    __tablename__ = "repository_index_pointers"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id"), primary_key=True
    )
    canonical_index_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("code_index_versions.id"), default=None
    )
    released_index_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("code_index_versions.id"), default=None
    )
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_by_event_id: Mapped[uuid.UUID | None] = mapped_column(default=None)


class CodeEntityChange(Base, UUIDPkMixin):
    __tablename__ = "code_entity_changes"
    __table_args__ = (
        Index("ix_code_entity_changes_repo_stable_key", "repository_id", "stable_key"),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repositories.id"))
    stable_key: Mapped[str] = mapped_column(String(512))
    change_kind: Mapped[EntityChangeKind]
    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executions.id"))
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"))
    candidate_commit_sha: Mapped[str] = mapped_column(String(64))
    integration_candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_candidates.id")
    )
    integrated_sha: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class SpecCodeLink(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "spec_code_links"
    __table_args__ = (
        Index("ix_scl_spec", "spec_lineage_key", "status"),
        Index("ix_scl_code", "repository_id", "code_stable_key", "status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    repository_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repositories.id"))
    spec_type: Mapped[str] = mapped_column(String(32))
    spec_id: Mapped[uuid.UUID] = mapped_column()
    spec_lineage_key: Mapped[str] = mapped_column(String(128))
    code_stable_key: Mapped[str] = mapped_column(String(512))
    relation: Mapped[SpecCodeLinkRelation]
    origin: Mapped[SpecCodeLinkOrigin]
    confidence: Mapped[float] = mapped_column(Float)
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id"), default=None)
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("executions.id"), default=None
    )
    commit_sha: Mapped[str | None] = mapped_column(String(64), default=None)
    evidence_refs: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    established_index_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("code_index_versions.id")
    )
    last_confirmed_index_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("code_index_versions.id")
    )
    status: Mapped[SpecCodeLinkStatus]
    promoted_from_link_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("spec_code_links.id"), default=None
    )
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
