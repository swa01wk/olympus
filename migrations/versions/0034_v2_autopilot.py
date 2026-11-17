"""v2 — Autopilot state per delivery cycle.

Revision ID: 0034_v2_autopilot
Revises: 0033_rl3_review_gates
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0034_v2_autopilot"
down_revision: str | None = "0033_rl3_review_gates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "autopilot_states",
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="WORKING"),
        sa.Column("step", sa.String(length=64), nullable=False, server_default="starting"),
        sa.Column("message", sa.Text(), nullable=False, server_default="Starting"),
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("failed_step", sa.String(length=64), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("retry_step", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["delivery_cycle_id"],
            ["delivery_cycles.id"],
            name=op.f("fk_autopilot_states_delivery_cycle_id_delivery_cycles"),
        ),
        sa.PrimaryKeyConstraint("delivery_cycle_id", name=op.f("pk_autopilot_states")),
    )


def downgrade() -> None:
    op.drop_table("autopilot_states")
