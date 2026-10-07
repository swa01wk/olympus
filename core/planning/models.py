from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPkMixin
from core.domain.enums import SpecStatus


class Architecture(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "architectures"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "lineage_key",
            "version",
            name="uq_architectures_project_lineage_version",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    lineage_key: Mapped[str] = mapped_column(String(128), default="ARCH")
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[SpecStatus] = mapped_column(index=True)
    kind: Mapped[str] = mapped_column(String(32))
    body: Mapped[dict[str, Any]] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64))
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("architectures.id"), default=None
    )
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("executions.id"), default=None
    )
    approval_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("approvals.id"), default=None)


class ArchitectureContract(Base, UUIDPkMixin):
    __tablename__ = "architecture_contracts"
    __table_args__ = (UniqueConstraint("architecture_id", "key"),)

    architecture_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("architectures.id"), index=True)
    key: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(512))
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)


class ImplementationSpec(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "implementation_specs"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "lineage_key",
            "version",
            name="uq_implementation_specs_project_lineage_version",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    lineage_key: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[SpecStatus] = mapped_column(index=True)
    kind: Mapped[str] = mapped_column(String(32))
    feature_spec_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("feature_specs.id"), index=True)
    architecture_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("architectures.id"), index=True)
    body: Mapped[dict[str, Any]] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64))
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("implementation_specs.id"), default=None
    )
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("executions.id"), default=None
    )
    approval_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("approvals.id"), default=None)
    conformance_report: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class TaskPlanRow(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "task_plans"

    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_cycles.id"), index=True
    )
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("executions.id"), default=None
    )
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifacts.id"), default=None)
    status: Mapped[str] = mapped_column(String(32), index=True)
    validation_report: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    implementation_spec_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    body: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class TaskSpecRef(Base):
    __tablename__ = "task_spec_refs"

    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    ref_type: Mapped[str] = mapped_column(String(64), primary_key=True)
    ref_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    ref_version: Mapped[int | None] = mapped_column(Integer, default=None)
