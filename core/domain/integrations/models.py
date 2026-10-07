"""Phase 16 integration domain models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from core.db.base import Base, TimestampMixin, UUIDPkMixin
from sqlalchemy import ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class StoredSecret(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "secrets"

    name: Mapped[str] = mapped_column(String(128), unique=True)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    rotated_at: Mapped[datetime | None] = mapped_column(default=None)


class ConnectorConfig(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "connector_configs"

    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"), default=None)
    connector: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(32))
    base_url: Mapped[str | None] = mapped_column(String(2048), default=None)
    secret_ref: Mapped[str | None] = mapped_column(String(512), default=None)
    enabled_actions: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    rate_limit: Mapped[int | None] = mapped_column(Integer, default=None)
    active: Mapped[bool] = mapped_column(default=True)


class ReconciliationItem(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "reconciliation_items"

    key: Mapped[str] = mapped_column(String(256), unique=True)
    kind: Mapped[str] = mapped_column(String(64))
    connector_action_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("connector_actions.id"), default=None
    )
    repository_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("repositories.id"), default=None
    )
    status: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(default=None)
    last_observation: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    correlation_id: Mapped[str] = mapped_column(String(128))
    resolved_by_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("actors.id"), default=None
    )
    resolution_note: Mapped[str | None] = mapped_column(Text, default=None)


class RepositoryEvent(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "repository_events"

    repository_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repositories.id"), index=True)
    inbound_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inbound_events.id"), default=None
    )
    ref: Mapped[str] = mapped_column(String(512))
    before_sha: Mapped[str | None] = mapped_column(String(64), default=None)
    after_sha: Mapped[str] = mapped_column(String(64))
    classification: Mapped[str] = mapped_column(String(64))
    processed_at: Mapped[datetime | None] = mapped_column(default=None)


class ExternalLink(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "external_links"

    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID] = mapped_column()
    provider: Mapped[str] = mapped_column(String(32))
    external_type: Mapped[str] = mapped_column(String(64))
    external_id: Mapped[str] = mapped_column(String(512))
    url: Mapped[str | None] = mapped_column(String(2048), default=None)

    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "entity_id",
            "provider",
            "external_type",
            "external_id",
        ),
    )


class DeploymentRecord(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "deployments"

    release_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("releases.id"), index=True)
    target: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    connector_action_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("connector_actions.id"))
    health: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
