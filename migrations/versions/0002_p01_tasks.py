"""Phase 01 — delivery cycles, tasks, contracts

Revision ID: 0002_p01_tasks
Revises: 0001_p01_repos
Create Date: 2026-10-01 22:31:30.947777

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_p01_tasks"
down_revision: str | None = "0001_p01_repos"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "delivery_cycles",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "GREENFIELD_BUILD",
                "BROWNFIELD_ONBOARDING",
                "FEATURE_CHANGE",
                "BUG_FIX",
                "REMEDIATION",
                name="deliverycycletype",
            ),
            nullable=False,
        ),
        sa.Column("objective", sa.String(length=4096), nullable=False),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=True),
        sa.Column("base_sha", sa.String(length=64), nullable=True),
        sa.Column("terminal_reason", sa.String(length=1024), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("opened_by_actor_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["opened_by_actor_id"],
            ["actors.id"],
            name=op.f("fk_delivery_cycles_opened_by_actor_id_actors"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_delivery_cycles_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name=op.f("fk_delivery_cycles_repository_id_repositories"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_delivery_cycles")),
        sa.UniqueConstraint("project_id", "key", name=op.f("uq_delivery_cycles_project_id")),
    )
    op.create_index(
        op.f("ix_delivery_cycles_project_id"), "delivery_cycles", ["project_id"], unique=False
    )
    op.create_table(
        "tasks",
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column(
            "work_type",
            sa.Enum(
                "ANALYSIS", "CODE_CHANGE", "VERIFICATION", "INTEGRATION", "RELEASE", name="worktype"
            ),
            nullable=False,
        ),
        sa.Column(
            "origin",
            sa.Enum(
                "IMPLEMENTATION_PLAN", "REMEDIATION", "REPAIR", "CONTROL_PLANE", name="taskorigin"
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "BLOCKED",
                "READY",
                "QUEUED",
                "RUNNING",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
                "STALE",
                "REVALIDATION_REQUIRED",
                name="taskstatus",
            ),
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("governing_ref_type", sa.String(length=64), nullable=True),
        sa.Column("governing_ref_id", sa.Uuid(), nullable=True),
        sa.Column("current_contract_id", sa.Uuid(), nullable=True),
        sa.Column("allow_parallel_executions", sa.Boolean(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("blocked_reason", sa.String(length=1024), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["current_contract_id"],
            ["task_contracts.id"],
            name="fk_tasks_current_contract_id",
            use_alter=True,
        ),
        sa.ForeignKeyConstraint(
            ["delivery_cycle_id"],
            ["delivery_cycles.id"],
            name=op.f("fk_tasks_delivery_cycle_id_delivery_cycles"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
        sa.UniqueConstraint("delivery_cycle_id", "key", name=op.f("uq_tasks_delivery_cycle_id")),
    )
    op.create_index(
        op.f("ix_tasks_delivery_cycle_id"), "tasks", ["delivery_cycle_id"], unique=False
    )
    op.create_index("ix_tasks_ready", "tasks", ["status", "priority", "created_at"], unique=False)
    op.create_index(op.f("ix_tasks_status"), "tasks", ["status"], unique=False)
    op.create_table(
        "task_contracts",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "ISSUED", "SUPERSEDED", name="taskcontractstatus"),
            nullable=False,
        ),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("compiled_by", sa.String(length=128), nullable=False),
        sa.Column("compiler_inputs_hash", sa.String(length=64), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_task_contracts_task_id_tasks")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_contracts")),
        sa.UniqueConstraint("task_id", "version", name=op.f("uq_task_contracts_task_id")),
    )
    op.create_index(op.f("ix_task_contracts_task_id"), "task_contracts", ["task_id"], unique=False)
    op.create_table(
        "task_dependencies",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("depends_on_task_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "task_id <> depends_on_task_id", name=op.f("ck_task_dependencies_no_self_dependency")
        ),
        sa.ForeignKeyConstraint(
            ["depends_on_task_id"],
            ["tasks.id"],
            name=op.f("fk_task_dependencies_depends_on_task_id_tasks"),
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_task_dependencies_task_id_tasks")
        ),
        sa.PrimaryKeyConstraint("task_id", "depends_on_task_id", name=op.f("pk_task_dependencies")),
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_task_contracts_one_issued
        ON task_contracts (task_id)
        WHERE status = 'ISSUED'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_task_contracts_one_issued")
    op.drop_table("task_dependencies")
    op.drop_index(op.f("ix_task_contracts_task_id"), table_name="task_contracts")
    op.drop_table("task_contracts")
    op.drop_index(op.f("ix_tasks_status"), table_name="tasks")
    op.drop_index("ix_tasks_ready", table_name="tasks")
    op.drop_index(op.f("ix_tasks_delivery_cycle_id"), table_name="tasks")
    op.drop_table("tasks")
    op.drop_index(op.f("ix_delivery_cycles_project_id"), table_name="delivery_cycles")
    op.drop_table("delivery_cycles")
    for enum_name in (
        "taskcontractstatus",
        "taskstatus",
        "taskorigin",
        "worktype",
        "deliverycycletype",
    ):
        op.execute(f'DROP TYPE IF EXISTS "{enum_name}" CASCADE')
