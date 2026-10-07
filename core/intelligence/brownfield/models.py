from __future__ import annotations

import uuid
from typing import Any

from core.db.base import Base, TimestampMixin, UUIDPkMixin
from core.intelligence.brownfield.enums import ObservedBehaviorKind, RecoveryProposalStatus
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class ObservedBehavior(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "observed_behaviors"
    __table_args__ = (
        UniqueConstraint("delivery_cycle_id", "key", name="uq_observed_behaviors_cycle_key"),
    )

    key: Mapped[str] = mapped_column(String(128))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_cycles.id"), index=True
    )
    index_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("code_index_versions.id"), index=True
    )
    commit_sha: Mapped[str] = mapped_column(String(64))
    kind: Mapped[ObservedBehaviorKind]
    description: Mapped[str] = mapped_column(String(2048))
    subject_stable_keys: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    evidence_refs: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    provenance: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float]
    passed: Mapped[bool | None] = mapped_column(default=None)
    fact_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_items.id"), index=True)


class RepositoryDiscovery(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "repository_discoveries"
    __table_args__ = (
        UniqueConstraint(
            "delivery_cycle_id",
            "commit_sha",
            name="uq_repository_discoveries_cycle_sha",
        ),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repositories.id"), index=True)
    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_cycles.id"), index=True
    )
    commit_sha: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64))


class RecoveredSpecEvidence(Base, UUIDPkMixin):
    __tablename__ = "recovered_spec_evidence"

    feature_spec_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("feature_specs.id"), index=True)
    element_type: Mapped[str] = mapped_column(String(32))
    element_key: Mapped[str] = mapped_column(String(128))
    support_type: Mapped[str] = mapped_column(String(32))
    support_ref: Mapped[str] = mapped_column(String(512))
    strength: Mapped[str] = mapped_column(String(16))


class RecoveryProposal(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "recovery_proposals"

    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_cycles.id"), index=True
    )
    survey_execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executions.id"))
    feature_execution_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    status: Mapped[RecoveryProposalStatus]
    validation_report: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    context_manifest_hash: Mapped[str] = mapped_column(String(64))
    reconciliation_report_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id"), default=None
    )
