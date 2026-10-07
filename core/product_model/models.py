from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPkMixin
from core.domain.enums import (
    DecompositionStatus,
    EntityStatus,
    EvidenceRequirement,
    KnowledgeClass,
    KnowledgeItemStatus,
    ModelOrigin,
    SpecKind,
    SpecStatus,
)


class ProductSource(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "product_sources"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "lineage_key",
            "version",
            name="uq_product_sources_project_lineage_version",
        ),
        UniqueConstraint(
            "project_id",
            "lineage_key",
            "content_hash",
            name="uq_product_sources_project_lineage_hash",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    delivery_cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("delivery_cycles.id"), index=True, default=None
    )
    lineage_key: Mapped[str] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(128))
    content_hash: Mapped[str] = mapped_column(String(64))
    raw_storage_ref: Mapped[str] = mapped_column(String(512))
    text_artifact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifacts.id"))
    inbound_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inbound_events.id"), default=None
    )
    created_by_actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("actors.id"))


class Capability(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "capabilities"
    __table_args__ = (UniqueConstraint("project_id", "key"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[EntityStatus] = mapped_column(default=EntityStatus.PROPOSED)
    origin: Mapped[ModelOrigin]
    source_refs: Mapped[list[Any]] = mapped_column(JSONB, default=list)


class Feature(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "features"
    __table_args__ = (UniqueConstraint("project_id", "key"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    capability_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("capabilities.id"), default=None
    )
    key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[EntityStatus] = mapped_column(default=EntityStatus.PROPOSED)
    origin: Mapped[ModelOrigin]
    source_refs: Mapped[list[Any]] = mapped_column(JSONB, default=list)


class FeatureSpec(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "feature_specs"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "lineage_key",
            "version",
            name="uq_feature_specs_project_lineage_version",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    feature_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("features.id"), index=True)
    lineage_key: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[SpecStatus] = mapped_column(index=True)
    spec_kind: Mapped[SpecKind] = mapped_column(default=SpecKind.CANONICAL)
    body: Mapped[dict[str, Any]] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64))
    derived_from_source_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_sources.id"), default=None
    )
    decomposition_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_decompositions.id"), default=None
    )
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("feature_specs.id"), default=None
    )
    promoted_from_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    approval_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("approvals.id"), default=None)
    confidence: Mapped[str | None] = mapped_column(String(16), default=None)
    claimed_confidence: Mapped[str | None] = mapped_column(String(16), default=None)
    uncertainty_count: Mapped[int | None] = mapped_column(Integer, default=None)


class Requirement(Base, UUIDPkMixin):
    __tablename__ = "requirements"
    __table_args__ = (UniqueConstraint("feature_spec_id", "lineage_key"),)

    feature_spec_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("feature_specs.id"), index=True)
    lineage_key: Mapped[str] = mapped_column(String(64))
    statement: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(32))
    priority: Mapped[str] = mapped_column(String(16))
    locked: Mapped[bool] = mapped_column(default=False)


class UserStory(Base, UUIDPkMixin):
    __tablename__ = "user_stories"
    __table_args__ = (UniqueConstraint("feature_spec_id", "lineage_key"),)

    feature_spec_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("feature_specs.id"), index=True)
    lineage_key: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(256))
    goal: Mapped[str] = mapped_column(Text)
    benefit: Mapped[str] = mapped_column(Text)
    locked: Mapped[bool] = mapped_column(default=False)


class AcceptanceCriterion(Base, UUIDPkMixin):
    __tablename__ = "acceptance_criteria"
    __table_args__ = (UniqueConstraint("feature_spec_id", "lineage_key"),)

    feature_spec_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("feature_specs.id"), index=True)
    lineage_key: Mapped[str] = mapped_column(String(64))
    statement: Mapped[str] = mapped_column(Text)
    given: Mapped[str | None] = mapped_column(Text, default=None)
    when: Mapped[str | None] = mapped_column(Text, default=None)
    then: Mapped[str | None] = mapped_column(Text, default=None)
    mandatory: Mapped[bool]
    evidence_requirement: Mapped[EvidenceRequirement]
    requirement_keys: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    change_kind: Mapped[str | None] = mapped_column(String(32), default=None)
    locked: Mapped[bool] = mapped_column(default=False)


class ProductDecomposition(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "product_decompositions"

    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_cycles.id"), index=True
    )
    product_source_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_sources.id"), index=True
    )
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("executions.id"), default=None
    )
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifacts.id"), default=None)
    status: Mapped[DecompositionStatus] = mapped_column(default=DecompositionStatus.PROPOSED)
    validation_report: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)


class KnowledgeItem(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "knowledge_items"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    delivery_cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("delivery_cycles.id"), index=True, default=None
    )
    knowledge_class: Mapped[KnowledgeClass] = mapped_column("class", String(32))
    statement: Mapped[str] = mapped_column(Text)
    subject_refs: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    evidence_refs: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    confidence: Mapped[str | None] = mapped_column(String(16), default=None)
    status: Mapped[KnowledgeItemStatus] = mapped_column(default=KnowledgeItemStatus.ACTIVE)
    blocking: Mapped[bool] = mapped_column(default=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_items.id"), default=None
    )


class ScopeSet(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "scope_sets"

    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_cycles.id"), index=True
    )
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by_actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("actors.id"))


class ScopeSetItem(Base):
    __tablename__ = "scope_set_items"

    scope_set_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope_sets.id"), primary_key=True)
    feature_spec_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feature_specs.id"), primary_key=True
    )
