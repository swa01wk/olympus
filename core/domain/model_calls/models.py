from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Index, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPkMixin


class ModelCall(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "model_calls"

    execution_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    delivery_cycle_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    agent_profile: Mapped[str] = mapped_column(String(128))
    purpose: Mapped[str] = mapped_column(String(256))
    alias: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(128))
    prompt_template_id: Mapped[str | None] = mapped_column(String(128))
    prompt_template_version: Mapped[str | None] = mapped_column(String(32))
    prompt_hash: Mapped[str] = mapped_column(String(64))
    output_schema: Mapped[str | None] = mapped_column(String(128))
    output_schema_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    latency_ms: Mapped[int] = mapped_column(default=0)
    cost_usd_estimate: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0)
    transport_retries: Mapped[int] = mapped_column(default=0)
    schema_retries: Mapped[int] = mapped_column(default=0)
    validation_errors: Mapped[list[Any] | None] = mapped_column(JSONB)
    provider_request_id: Mapped[str | None] = mapped_column(String(128))
    correlation_id: Mapped[str] = mapped_column(String(128))
    response_artifact_ref: Mapped[str | None] = mapped_column(String(512))
    raw_prompt_ref: Mapped[str | None] = mapped_column(String(512), default=None)
    raw_response_ref: Mapped[str | None] = mapped_column(String(512), default=None)
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    __table_args__ = (Index("ix_model_calls_exec", "execution_id", "created_at"),)
