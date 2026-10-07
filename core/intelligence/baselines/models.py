from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPkMixin
from core.intelligence.baselines.enums import (
    BaselineActivation,
    BaselineCheckKind,
    BaselineSource,
    BaselineStatus,
    ReadinessResult,
)


class BehavioralBaseline(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "behavioral_baselines"
    __table_args__ = (
        UniqueConstraint("project_id", "lineage_key", "version", name="uq_baselines_lineage_ver"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    lineage_key: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[BaselineStatus] = mapped_column(index=True)
    source: Mapped[BaselineSource]
    given: Mapped[str] = mapped_column(Text)
    when: Mapped[str] = mapped_column(Text)
    then: Mapped[str] = mapped_column(Text)
    check_kind: Mapped[BaselineCheckKind]
    check_ref: Mapped[str] = mapped_column(String(512))
    check_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id"), default=None
    )
    feature_spec_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("feature_specs.id"), default=None
    )
    ac_lineage_key: Mapped[str | None] = mapped_column(String(64), default=None)
    observed_behavior_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    exercised_stable_keys: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    established_sha: Mapped[str] = mapped_column(String(64))
    established_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence.id"), default=None
    )
    activation: Mapped[BaselineActivation | None] = mapped_column(String(32), default=None)


class BaselineSet(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "baseline_sets"
    __table_args__ = (UniqueConstraint("project_id", "key", name="uq_baseline_sets_project_key"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    key: Mapped[str] = mapped_column(String(16))
    commit_sha: Mapped[str] = mapped_column(String(64))
    content_hash: Mapped[str] = mapped_column(String(64))
    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("delivery_cycles.id"))


class BaselineSetItem(Base, UUIDPkMixin):
    __tablename__ = "baseline_set_items"
    __table_args__ = (
        UniqueConstraint("baseline_set_id", "baseline_id", name="uq_baseline_set_items"),
    )

    baseline_set_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("baseline_sets.id"))
    baseline_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("behavioral_baselines.id"))


class PromotionDecision(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "promotion_decisions"
    __table_args__ = (
        UniqueConstraint(
            "delivery_cycle_id",
            "subject_type",
            "subject_id",
            name="uq_promotion_decisions_cycle_subject",
        ),
    )

    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_cycles.id"), index=True
    )
    subject_type: Mapped[str] = mapped_column(String(64))
    subject_id: Mapped[uuid.UUID]
    decision: Mapped[str] = mapped_column(String(64))
    approval_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("approvals.id"), default=None)
    decided_by_actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("actors.id"))
    note: Mapped[str | None] = mapped_column(Text, default=None)
    result_refs: Mapped[list[Any]] = mapped_column(JSONB, default=list)


class ReadinessAssessment(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "readiness_assessments"

    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_cycles.id"), index=True
    )
    commit_sha: Mapped[str] = mapped_column(String(64))
    index_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("code_index_versions.id"))
    canonical_revision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repository_revisions.id"))
    metrics: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    result: Mapped[ReadinessResult]
    remediable: Mapped[bool]
    reasons: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    policy_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("policy_versions.id"))
