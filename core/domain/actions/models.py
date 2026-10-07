from __future__ import annotations

import uuid
from typing import Any

from core.db.base import Base, TimestampMixin, UUIDPkMixin
from core.domain.enums import ActionStatus
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class ActionRequest(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "action_requests"

    key: Mapped[str] = mapped_column(String(64), index=True)
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("executions.id"), index=True, default=None
    )
    lease_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("actors.id"))
    agent_profile: Mapped[str | None] = mapped_column(String(128), default=None)
    tool: Mapped[str] = mapped_column(String(128))
    resource: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    params_hash: Mapped[str] = mapped_column(String(64))
    task_contract_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("task_contracts.id"), default=None
    )
    task_contract_version: Mapped[int | None] = mapped_column(Integer, default=None)
    idempotency_key: Mapped[str | None] = mapped_column(String(256), default=None)
    correlation_id: Mapped[str] = mapped_column(String(128))
    status: Mapped[ActionStatus]
    policy_decision: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    approval_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("approvals.id"), default=None)


class ActionResult(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "action_results"

    action_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("action_requests.id"), unique=True
    )
    status: Mapped[str] = mapped_column(String(32))
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    output_ref: Mapped[str | None] = mapped_column(String(512), default=None)
    error_class: Mapped[str | None] = mapped_column(String(64), default=None)
    error_detail: Mapped[str | None] = mapped_column(String(2048), default=None)
    duration_ms: Mapped[int] = mapped_column(Integer)
    connector_action_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
