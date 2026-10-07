from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPkMixin
from core.integration.enums import ICStatus


class IntegrationCandidate(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "integration_candidates"
    __table_args__ = (
        UniqueConstraint("delivery_cycle_id", "key", name="uq_integration_candidates_cycle_key"),
    )

    key: Mapped[str] = mapped_column(String(64))
    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_cycles.id"), index=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repositories.id"), index=True)
    base_sha: Mapped[str] = mapped_column(String(64))
    integration_branch: Mapped[str] = mapped_column(String(256))
    integrated_sha: Mapped[str | None] = mapped_column(String(64), default=None)
    status: Mapped[ICStatus]
    ordering: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    integration_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("executions.id"), default=None
    )
    checks_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id"), default=None
    )
    canonical_index_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("code_index_versions.id"), default=None
    )
    canonical_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("repository_revisions.id"), default=None
    )
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("integration_candidates.id"), default=None
    )
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class IntegrationCandidateCommit(Base, UUIDPkMixin):
    __tablename__ = "integration_candidate_commits"
    __table_args__ = (
        UniqueConstraint(
            "integration_candidate_id",
            "candidate_commit_id",
            name="uq_ic_commits_ic_candidate",
        ),
    )

    integration_candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_candidates.id")
    )
    candidate_commit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidate_commits.id"))
    position: Mapped[int] = mapped_column(Integer)
    included: Mapped[bool] = mapped_column(default=True)
    skip_reason: Mapped[str | None] = mapped_column(String(256), default=None)
