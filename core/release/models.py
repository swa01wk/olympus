from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPkMixin
from core.release.enums import ReleaseStatus


class Release(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "releases"
    __table_args__ = (UniqueConstraint("project_id", "key"),)

    key: Mapped[str] = mapped_column(String(64))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_cycles.id"), index=True
    )
    integration_candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_candidates.id")
    )
    integrated_sha: Mapped[str] = mapped_column(String(64))
    status: Mapped[ReleaseStatus]
    manifest_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("release_manifests.id"), default=None
    )
    approval_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("approvals.id"), default=None)
    release_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("executions.id"), default=None
    )
    tag: Mapped[str | None] = mapped_column(String(256), default=None)
    released_at: Mapped[datetime | None] = mapped_column(default=None)
    latest_eligibility_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("release_eligibility_evaluations.id"), default=None
    )


class ReleaseManifest(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "release_manifests"

    release_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("releases.id"), index=True)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64))


class ReleaseEligibilityEvaluation(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "release_eligibility_evaluations"

    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_cycles.id"), index=True
    )
    integration_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("integration_candidates.id"), default=None
    )
    eligible: Mapped[bool]
    conditions: Mapped[list[Any]] = mapped_column(JSONB)
    policy_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("policy_versions.id"))
    trigger_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("domain_events.id"), default=None
    )


class DeliveryOutcome(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "delivery_outcomes"

    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_cycles.id"), unique=True
    )
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result: Mapped[str] = mapped_column(String(32))
