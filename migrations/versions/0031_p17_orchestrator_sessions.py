"""Phase 17 — orchestrator UI sessions (non-canonical conversation)

Revision ID: 0031_p17_orchestrator
Revises: 0030_p16_integrations
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0031_p17_orchestrator"
down_revision: str | None = "0030_p16_integrations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "orchestrator_sessions",
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=True),
        sa.Column(
            "turns", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["actors.id"], name=op.f("fk_orchestrator_sessions_actor_id_actors")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_orchestrator_sessions_project_id_projects"),
        ),
        sa.ForeignKeyConstraint(
            ["delivery_cycle_id"],
            ["delivery_cycles.id"],
            name=op.f("fk_orchestrator_sessions_delivery_cycle_id_delivery_cycles"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orchestrator_sessions")),
    )
    op.create_index(
        op.f("ix_orchestrator_sessions_actor_id"),
        "orchestrator_sessions",
        ["actor_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_orchestrator_sessions_actor_id"), table_name="orchestrator_sessions")
    op.drop_table("orchestrator_sessions")
