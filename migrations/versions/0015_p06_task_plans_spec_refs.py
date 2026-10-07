"""Phase 06 — task_plans, task_spec_refs, tasks.implementation_spec_id

Revision ID: 0015_p06_task_plans
Revises: 0014_p06_implementation_specs
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_p06_task_plans"
down_revision: str | None = "0014_p06_implementation_specs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_plans",
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=True),
        sa.Column("artifact_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "validation_report",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "implementation_spec_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "body", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"]),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_plans_delivery_cycle_id", "task_plans", ["delivery_cycle_id"])
    op.create_index("ix_task_plans_status", "task_plans", ["status"])

    op.create_table(
        "task_spec_refs",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("ref_type", sa.String(length=64), nullable=False),
        sa.Column("ref_id", sa.Uuid(), nullable=False),
        sa.Column("ref_version", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("task_id", "ref_type", "ref_id"),
    )

    op.add_column("tasks", sa.Column("implementation_spec_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_tasks_implementation_spec_id",
        "tasks",
        "implementation_specs",
        ["implementation_spec_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_tasks_implementation_spec_id", "tasks", type_="foreignkey")
    op.drop_column("tasks", "implementation_spec_id")
    op.drop_table("task_spec_refs")
    op.drop_table("task_plans")
