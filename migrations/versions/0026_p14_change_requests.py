"""Phase 14 — change requests for Feature Change journey.

Revision ID: 0026_p14_change_requests
Revises: 0025_p13_spec_deltas_impact
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0026_p14_change_requests"
down_revision: str | None = "0025_p13_spec_deltas_impact"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "change_requests",
        sa.Column("key", sa.String(length=16), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("external_ref", sa.String(length=256), nullable=True),
        sa.Column("inbound_event_id", sa.Uuid(), nullable=True),
        sa.Column("product_source_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("resolved_feature_id", sa.Uuid(), nullable=True),
        sa.Column("spec_delta_id", sa.Uuid(), nullable=True),
        sa.Column("release_id", sa.Uuid(), nullable=True),
        sa.Column("interpretation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("interpretation_execution_id", sa.Uuid(), nullable=True),
        sa.Column("candidate_features", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.ForeignKeyConstraint(["inbound_event_id"], ["inbound_events.id"]),
        sa.ForeignKeyConstraint(["product_source_id"], ["product_sources.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["release_id"], ["releases.id"]),
        sa.ForeignKeyConstraint(["resolved_feature_id"], ["features.id"]),
        sa.ForeignKeyConstraint(["spec_delta_id"], ["spec_deltas.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "source_type", "external_ref"),
    )
    op.create_index("ix_change_requests_project_id", "change_requests", ["project_id"])
    op.create_index(
        "ix_change_requests_delivery_cycle_id", "change_requests", ["delivery_cycle_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_change_requests_delivery_cycle_id", table_name="change_requests")
    op.drop_index("ix_change_requests_project_id", table_name="change_requests")
    op.drop_table("change_requests")
