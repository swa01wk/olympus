from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPkMixin


class Defect(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "defects"
    __table_args__ = (UniqueConstraint("project_id", "source_type", "external_ref"),)

    key: Mapped[str] = mapped_column(String(16))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    delivery_cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("delivery_cycles.id"), default=None, index=True
    )
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text())
    product_source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product_sources.id"))
    source_type: Mapped[str] = mapped_column(String(64))
    external_ref: Mapped[str | None] = mapped_column(String(256), default=None)
    inbound_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inbound_events.id"), default=None
    )
    affected_release_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("releases.id"), default=None
    )
    affected_sha: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str | None] = mapped_column(String(8), default=None)
    status: Mapped[str] = mapped_column(String(32))
    triage: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    linked_feature_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    expected_ac_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    unlinked_acknowledged: Mapped[bool] = mapped_column(default=False)


class Reproduction(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "reproductions"

    defect_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("defects.id"), index=True)
    phase: Mapped[str] = mapped_column(String(32))
    commit_sha: Mapped[str] = mapped_column(String(64))
    artifact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifacts.id"))
    artifact_hash: Mapped[str] = mapped_column(String(64))
    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executions.id"))
    outcome: Mapped[str] = mapped_column(String(32))
    signature_matched: Mapped[bool] = mapped_column(default=False)
    runs: Mapped[int] = mapped_column(default=1)
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("evidence.id"), default=None)
    junit_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id"), default=None
    )


class TraceCorrelation(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "trace_correlations"

    reproduction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reproductions.id"), index=True)
    index_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("code_index_versions.id"))
    entry_route_key: Mapped[str | None] = mapped_column(String(256), default=None)
    traceback_stable_keys: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    executed_stable_keys: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    candidates: Mapped[list[Any]] = mapped_column(JSONB, default=list)


class RootCauseAnalysis(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "root_cause_analyses"

    defect_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("defects.id"), index=True)
    trace_correlation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trace_correlations.id"))
    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executions.id"))
    faulty_stable_keys: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    explanation: Mapped[str] = mapped_column(Text())
    knowledge_class: Mapped[str] = mapped_column(String(32), default="INFERENCE")
    confidence: Mapped[float] = mapped_column(default=0.0)
    fix_outline: Mapped[str] = mapped_column(Text(), default="")
    regression_risks: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    cited_evidence_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    impact_assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("impact_assessments.id"), default=None
    )
    status: Mapped[str] = mapped_column(String(32))


class ExpectedBehaviorResolution(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "expected_behavior_resolutions"

    defect_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("defects.id"), index=True)
    classification: Mapped[str] = mapped_column(String(32))
    resolution_kind: Mapped[str] = mapped_column(String(32))
    ac_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    contradicted_baseline_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    spec_delta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("spec_deltas.id"), default=None
    )
    approval_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("approvals.id"), default=None)
    statement: Mapped[str] = mapped_column(Text())
    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executions.id"))
