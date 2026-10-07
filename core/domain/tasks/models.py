from __future__ import annotations

import uuid

from core.db.base import Base, TimestampMixin, UUIDPkMixin
from core.domain.enums import TaskOrigin, TaskStatus, WorkType
from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class Task(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("delivery_cycle_id", "key"),
        Index("ix_tasks_ready", "status", "priority", "created_at"),
    )

    delivery_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_cycles.id"), index=True
    )
    key: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(512))
    work_type: Mapped[WorkType]
    origin: Mapped[TaskOrigin]
    status: Mapped[TaskStatus] = mapped_column(default=TaskStatus.DRAFT, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    governing_ref_type: Mapped[str | None] = mapped_column(String(64), default=None)
    governing_ref_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    current_contract_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("task_contracts.id", use_alter=True, name="fk_tasks_current_contract_id"),
        default=None,
    )
    allow_parallel_executions: Mapped[bool] = mapped_column(default=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    blocked_reason: Mapped[str | None] = mapped_column(String(1024), default=None)
    implementation_spec_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "implementation_specs.id",
            use_alter=True,
            name="fk_tasks_implementation_spec_id",
        ),
        default=None,
    )


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (CheckConstraint("task_id <> depends_on_task_id", name="no_self_dependency"),)

    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    depends_on_task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), default="FINISH_TO_START")
