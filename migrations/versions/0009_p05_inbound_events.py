"""Phase 05 — inbound integration sources and events

Revision ID: 0009_p05_inbound
Revises: 0008_p04_workspaces
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_p05_inbound"
down_revision: str | None = "0008_p04_workspaces"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_sources",
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("auth_kind", sa.String(length=32), nullable=False),
        sa.Column("secret_ref", sa.String(length=256), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_integration_sources_source_type", "integration_sources", ["source_type"])

    op.create_table(
        "inbound_events",
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=256), nullable=False),
        sa.Column("event_id", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("payload_storage_ref", sa.String(length=512), nullable=True),
        sa.Column("payload_inline", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("normalized", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("command_log_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["actors.id"]),
        sa.ForeignKeyConstraint(["command_log_id"], ["command_log.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_type", "source_id", "event_id"),
    )
    op.create_index("ix_inbound_events_status", "inbound_events", ["status"])


def downgrade() -> None:
    op.drop_table("inbound_events")
    op.drop_table("integration_sources")
