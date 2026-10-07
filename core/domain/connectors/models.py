from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from core.db.base import Base, TimestampMixin, UUIDPkMixin
from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class ConnectorActionRecord(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "connector_actions"

    connector: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    action_request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("action_requests.id"))
    execution_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    task_contract_ref: Mapped[str | None] = mapped_column(String(128), default=None)
    target_resource: Mapped[str] = mapped_column(String(512))
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    correlation_id: Mapped[str] = mapped_column(String(128))
    policy_context: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    expected_result_schema: Mapped[str] = mapped_column(String(128))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32))
    external_ref: Mapped[str | None] = mapped_column(String(512), default=None)

    __table_args__ = (UniqueConstraint("connector", "idempotency_key"),)


class ConnectorResultRecord(Base, UUIDPkMixin):
    __tablename__ = "connector_results"

    connector_action_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connector_actions.id"), index=True
    )
    attempt: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32))
    normalized_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    raw_ref: Mapped[str | None] = mapped_column(String(512), default=None)
    external_ref: Mapped[str | None] = mapped_column(String(512), default=None)
    error_class: Mapped[str | None] = mapped_column(String(64), default=None)
    received_at: Mapped[datetime] = mapped_column(server_default=func.now())
