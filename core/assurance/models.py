from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.assurance.enums import (
    EvidenceProducer,
    EvidenceResult,
    EvidenceType,
    GateStatus,
    GateType,
    ObligationReason,
    ObligationStatus,
    VerificationPlanStatus,
)
from core.db.base import Base, TimestampMixin, UUIDPkMixin
from core.integration.enums import FindingSeverity, FindingSource, FindingStatus


class Evidence(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "evidence"
    __table_args__ = (UniqueConstraint("project_id", "key", name="uq_evidence_project_key"),)

    key: Mapped[str] = mapped_column(String(64))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_cycles.id"), index=True
    )
    integration_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("integration_candidates.id"), default=None, index=True
    )
    commit_sha: Mapped[str] = mapped_column(String(64))
    evidence_type: Mapped[EvidenceType]
    result: Mapped[EvidenceResult]
    subject_type: Mapped[str] = mapped_column(String(32))
    subject_id: Mapped[uuid.UUID]
    obligation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("verification_obligations.id"), default=None
    )
    check_ref: Mapped[str] = mapped_column(String(512))
    check_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id"), default=None
    )
    log_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id"), default=None
    )
    producer: Mapped[EvidenceProducer]
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("executions.id"), default=None
    )
    carried_forward_from_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence.id"), default=None
    )
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class VerificationObligation(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "verification_obligations"
    __table_args__ = (
        UniqueConstraint(
            "integration_candidate_id",
            "subject_type",
            "subject_id",
            "gate_type",
            name="uq_obligations_ic_subject_gate",
        ),
    )

    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_cycles.id"), index=True
    )
    integration_candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_candidates.id"), index=True
    )
    gate_type: Mapped[str] = mapped_column(String(32))
    subject_type: Mapped[str] = mapped_column(String(32))
    subject_id: Mapped[uuid.UUID]
    subject_key: Mapped[str] = mapped_column(String(128))
    required: Mapped[bool]
    allowed_evidence_types: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    reason: Mapped[ObligationReason]
    source_refs: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    status: Mapped[ObligationStatus] = mapped_column(default=ObligationStatus.OPEN)


class AcceptanceCoverage(Base, UUIDPkMixin):
    __tablename__ = "acceptance_coverage"

    obligation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("verification_obligations.id"), index=True
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence.id"), index=True)
    satisfied: Mapped[bool]
    computed_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Gate(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "gates"
    __table_args__ = (
        UniqueConstraint("integration_candidate_id", "gate_type"),
        UniqueConstraint("delivery_cycle_id", "key", name="uq_gates_cycle_key"),
    )

    key: Mapped[str] = mapped_column(String(64))
    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_cycles.id"), index=True
    )
    integration_candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_candidates.id"), index=True
    )
    gate_type: Mapped[GateType]
    status: Mapped[GateStatus] = mapped_column(default=GateStatus.PENDING)
    recommendation: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    reasons: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    inputs_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    policy_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("policy_versions.id"), default=None
    )
    finalized_at: Mapped[datetime | None] = mapped_column(default=None)
    finalized_by: Mapped[str | None] = mapped_column(String(128), default=None)


class VerificationPlanRow(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "verification_plans"

    integration_candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_candidates.id"), index=True
    )
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("executions.id"), default=None
    )
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifacts.id"), default=None)
    status: Mapped[VerificationPlanStatus] = mapped_column(default=VerificationPlanStatus.PROPOSED)
    validation_report: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class WardenReviewRecord(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "reviews"

    integration_candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_candidates.id"), index=True
    )
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("executions.id"), default=None
    )
    recommendation: Mapped[str] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(String(4096))
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifacts.id"), default=None)


class Finding(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "findings"
    __table_args__ = (UniqueConstraint("project_id", "key", name="uq_findings_project_key"),)

    key: Mapped[str] = mapped_column(String(64))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_cycles.id"), index=True
    )
    integration_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("integration_candidates.id"), default=None
    )
    commit_sha: Mapped[str | None] = mapped_column(String(64), default=None)
    source: Mapped[FindingSource]
    category: Mapped[str] = mapped_column(String(64))
    severity: Mapped[FindingSeverity]
    blocking: Mapped[bool] = mapped_column(default=False)
    title: Mapped[str] = mapped_column(String(512))
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    code_refs: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    spec_refs: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    status: Mapped[FindingStatus]
    remediation_task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tasks.id"), default=None
    )
    waiver_approval_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("approvals.id"), default=None
    )
    resolved_by_ic_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("integration_candidates.id"), default=None
    )
    producer_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("executions.id"), default=None
    )
    fingerprint: Mapped[str | None] = mapped_column(String(64), default=None, index=True)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
