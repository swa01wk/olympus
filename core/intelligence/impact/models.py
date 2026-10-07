from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Float, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPkMixin


class SpecDelta(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "spec_deltas"
    __table_args__ = (UniqueConstraint("project_id", "key", name="uq_spec_deltas_project_key"),)

    key: Mapped[str] = mapped_column(String(16))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_cycles.id"), index=True
    )
    feature_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("features.id"), index=True)
    from_spec_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("feature_specs.id"), default=None
    )
    to_spec_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("feature_specs.id"), index=True)
    changes: Mapped[dict[str, Any]] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64))
    approval_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("approvals.id"), default=None)
    status: Mapped[str] = mapped_column(String(32), index=True)


class ImpactAssessment(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "impact_assessments"
    __table_args__ = (UniqueConstraint("delivery_cycle_id", "key", name="uq_ia_cycle_key"),)

    key: Mapped[str] = mapped_column(String(16))
    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_cycles.id"), index=True
    )
    index_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("code_index_versions.id"))
    commit_sha: Mapped[str] = mapped_column(String(64))
    seed_kind: Mapped[str] = mapped_column(String(32))
    spec_delta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("spec_deltas.id"), default=None
    )
    seed_refs: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(32), index=True)
    architecture_delta_suggested: Mapped[bool] = mapped_column(Boolean, default=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    policy_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("policy_versions.id"), default=None
    )
    content_hash: Mapped[str] = mapped_column(String(64))


class ImpactItem(Base, UUIDPkMixin):
    __tablename__ = "impact_items"
    __table_args__ = (Index("ix_impact_items_assessment_id", "impact_assessment_id"),)

    impact_assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("impact_assessments.id"), index=True
    )
    item_type: Mapped[str] = mapped_column(String(32))
    ref: Mapped[str] = mapped_column(String(512))
    impact_kind: Mapped[str] = mapped_column(String(32))
    retrieval_source: Mapped[str] = mapped_column(String(32))
    path: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    contract_surface: Mapped[bool] = mapped_column(Boolean, default=False)
    rationale: Mapped[str] = mapped_column(Text, default="")
    selected_for_verification: Mapped[bool] = mapped_column(Boolean, default=False)


class Embedding(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "embeddings"
    __table_args__ = (
        UniqueConstraint(
            "subject_type",
            "subject_key",
            "content_hash",
            "model",
            name="uq_embeddings_subject_hash_model",
        ),
    )

    subject_type: Mapped[str] = mapped_column(String(32))
    subject_key: Mapped[str] = mapped_column(String(512))
    repository_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("repositories.id"), default=None
    )
    content_hash: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    dim: Mapped[int] = mapped_column()
    vector: Mapped[list[float]] = mapped_column(Vector(1536))


class StalenessEvent(Base, UUIDPkMixin):
    __tablename__ = "staleness_events"
    __table_args__ = (Index("ix_staleness_events_subject", "subject_type", "subject_id"),)

    subject_type: Mapped[str] = mapped_column(String(32))
    subject_id: Mapped[uuid.UUID] = mapped_column()
    from_status: Mapped[str | None] = mapped_column(String(32), default=None)
    to_status: Mapped[str] = mapped_column(String(32))
    cause_type: Mapped[str] = mapped_column(String(64))
    cause_ref: Mapped[str | None] = mapped_column(String(512), default=None)
    delivery_cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("delivery_cycles.id"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
