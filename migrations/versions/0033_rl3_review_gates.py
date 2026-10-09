"""RL3 — review gates, expected behaviour, task plans, provisional baselines.

Revision ID: 0033_rl3_review_gates
Revises: 0032_p18_security_observability
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0033_rl3_review_gates"
down_revision: str | None = "0032_p18_security_observability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE approvaltype ADD VALUE IF NOT EXISTS 'EXPECTED_BEHAVIOR'")
        op.execute("ALTER TYPE approvaltype ADD VALUE IF NOT EXISTS 'TASK_PLAN'")

    op.add_column(
        "expected_behavior_resolutions",
        sa.Column(
            "contradicted_baseline_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "behavioral_baselines",
        sa.Column("provisional", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("behavioral_baselines", "provisional")
    op.drop_column("expected_behavior_resolutions", "contradicted_baseline_ids")
    # PostgreSQL enum values cannot be removed; TASK_PLAN may remain on approvaltype.
