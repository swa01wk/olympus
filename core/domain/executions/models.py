from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPkMixin
from core.domain.enums import (
    CheckpointReason,
    CheckpointResolution,
    ClarificationStatus,
    ExecutionStatus,
    LeaseState,
)


class Execution(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "executions"

    key: Mapped[str] = mapped_column(String(64))
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), index=True)
    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(index=True)
    task_contract_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("task_contracts.id"))
    attempt_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[ExecutionStatus] = mapped_column(index=True)
    executor_kind: Mapped[str] = mapped_column(String(32))
    agent_profile: Mapped[str | None] = mapped_column(String(128), default=None)
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("execution_snapshots.id", use_alter=True, name="fk_executions_snapshot_id"),
        default=None,
    )
    previous_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("executions.id"), default=None
    )
    failure_class: Mapped[str | None] = mapped_column(String(64), default=None)
    failure_detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    retriable: Mapped[bool | None] = mapped_column(default=None)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    runtime_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
    lease_attempts: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("task_id", "attempt_number"),
        Index(
            "uq_one_active_exec_per_task",
            "task_id",
            unique=True,
            postgresql_where=text(
                "status IN ('QUEUED','LEASED','STARTED','OUTPUT_PRODUCED','VALIDATING','COMMITTED')"
            ),
        ),
    )


class ExecutionSnapshot(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "execution_snapshots"

    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executions.id"), unique=True)
    task_contract_id: Mapped[uuid.UUID]
    task_contract_version: Mapped[int]
    task_contract_hash: Mapped[str] = mapped_column(String(64))
    base_commit: Mapped[str | None] = mapped_column(String(64), default=None)
    repository_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    policy_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("policy_versions.id"))
    risk_tier: Mapped[str] = mapped_column(String(32))
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    snapshot_hash: Mapped[str] = mapped_column(String(64), index=True)


class ExecutionLease(Base, UUIDPkMixin):
    __tablename__ = "execution_leases"

    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executions.id"), index=True)
    worker_id: Mapped[str] = mapped_column(String(256))
    acquired_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    heartbeat_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    expires_at: Mapped[datetime]
    released_at: Mapped[datetime | None] = mapped_column(default=None)
    state: Mapped[LeaseState] = mapped_column(default=LeaseState.ACTIVE)

    __table_args__ = (
        Index(
            "uq_one_active_lease_per_execution",
            "execution_id",
            unique=True,
            postgresql_where=text("state = 'ACTIVE'"),
        ),
    )


class ExecutionEvent(Base, UUIDPkMixin):
    __tablename__ = "execution_events"

    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executions.id"), index=True)
    seq: Mapped[int]
    type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    __table_args__ = (UniqueConstraint("execution_id", "seq"),)


class Checkpoint(Base, UUIDPkMixin):
    __tablename__ = "checkpoints"

    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executions.id"), index=True)
    reason: Mapped[CheckpointReason]
    pending_ref_type: Mapped[str] = mapped_column(String(64))
    pending_ref_id: Mapped[uuid.UUID]
    continuation: Mapped[dict[str, Any]] = mapped_column(JSONB)
    runtime_checkpoint_ref: Mapped[str | None] = mapped_column(String(512), default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    resolved_at: Mapped[datetime | None] = mapped_column(default=None)
    resolution: Mapped[CheckpointResolution | None] = mapped_column(default=None)


class Clarification(Base, UUIDPkMixin):
    __tablename__ = "clarifications"

    key: Mapped[str] = mapped_column(String(64))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_cycles.id"), index=True
    )
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("executions.id"), default=None
    )
    question: Mapped[str] = mapped_column(Text)
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    options: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    blocking: Mapped[bool] = mapped_column(default=True)
    status: Mapped[ClarificationStatus] = mapped_column(default=ClarificationStatus.OPEN)
    answer: Mapped[str | None] = mapped_column(Text, default=None)
    answered_by_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("actors.id"), default=None
    )
    answered_at: Mapped[datetime | None] = mapped_column(default=None)
