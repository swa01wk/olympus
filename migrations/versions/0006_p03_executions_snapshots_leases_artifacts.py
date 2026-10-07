"""Phase 03 — executions, snapshots, leases, artifacts, checkpoints

Revision ID: 0006_p03_executions
Revises: 0005_p02_model_calls
Create Date: 2026-10-02 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_p03_executions"
down_revision: str | None = "0005_p02_model_calls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "executions",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("task_contract_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("executor_kind", sa.String(length=32), nullable=False),
        sa.Column("agent_profile", sa.String(length=128), nullable=True),
        sa.Column("snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("previous_execution_id", sa.Uuid(), nullable=True),
        sa.Column("failure_class", sa.String(length=64), nullable=True),
        sa.Column("failure_detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("retriable", sa.Boolean(), nullable=True),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("runtime_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("lease_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["previous_execution_id"],
            ["executions.id"],
            name=op.f("fk_executions_previous_execution_id_executions"),
        ),
        sa.ForeignKeyConstraint(
            ["task_contract_id"],
            ["task_contracts.id"],
            name=op.f("fk_executions_task_contract_id_task_contracts"),
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_executions_task_id_tasks")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_executions")),
        sa.UniqueConstraint("task_id", "attempt_number", name=op.f("uq_executions_task_id")),
    )
    op.create_index(op.f("ix_executions_delivery_cycle_id"), "executions", ["delivery_cycle_id"])
    op.create_index(op.f("ix_executions_status"), "executions", ["status"])
    op.create_index(op.f("ix_executions_task_id"), "executions", ["task_id"])
    op.create_index(
        "uq_one_active_exec_per_task",
        "executions",
        ["task_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('QUEUED','LEASED','STARTED','OUTPUT_PRODUCED','VALIDATING','COMMITTED')"
        ),
    )

    op.create_table(
        "execution_snapshots",
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("task_contract_id", sa.Uuid(), nullable=False),
        sa.Column("task_contract_version", sa.Integer(), nullable=False),
        sa.Column("task_contract_hash", sa.String(length=64), nullable=False),
        sa.Column("base_commit", sa.String(length=64), nullable=True),
        sa.Column("repository_id", sa.Uuid(), nullable=True),
        sa.Column("policy_version_id", sa.Uuid(), nullable=False),
        sa.Column("risk_tier", sa.String(length=32), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["executions.id"],
            name=op.f("fk_execution_snapshots_execution_id_executions"),
        ),
        sa.ForeignKeyConstraint(
            ["policy_version_id"],
            ["policy_versions.id"],
            name=op.f("fk_execution_snapshots_policy_version_id_policy_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_execution_snapshots")),
        sa.UniqueConstraint("execution_id", name=op.f("uq_execution_snapshots_execution_id")),
    )
    op.create_index(
        op.f("ix_execution_snapshots_snapshot_hash"),
        "execution_snapshots",
        ["snapshot_hash"],
    )

    op.create_foreign_key(
        op.f("fk_executions_snapshot_id_execution_snapshots"),
        "executions",
        "execution_snapshots",
        ["snapshot_id"],
        ["id"],
        use_alter=True,
    )

    op.create_table(
        "execution_leases",
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("worker_id", sa.String(length=256), nullable=False),
        sa.Column("acquired_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["executions.id"],
            name=op.f("fk_execution_leases_execution_id_executions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_execution_leases")),
    )
    op.create_index(op.f("ix_execution_leases_execution_id"), "execution_leases", ["execution_id"])
    op.create_index(
        "uq_one_active_lease_per_execution",
        "execution_leases",
        ["execution_id"],
        unique=True,
        postgresql_where=sa.text("state = 'ACTIVE'"),
    )

    op.create_table(
        "artifacts",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=True),
        sa.Column("execution_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=128), nullable=False),
        sa.Column("schema_name", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_ref", sa.String(length=512), nullable=False),
        sa.Column("inline", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by_actor_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_actor_id"],
            ["actors.id"],
            name=op.f("fk_artifacts_created_by_actor_id_actors"),
        ),
        sa.ForeignKeyConstraint(
            ["delivery_cycle_id"],
            ["delivery_cycles.id"],
            name=op.f("fk_artifacts_delivery_cycle_id_delivery_cycles"),
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["executions.id"],
            name=op.f("fk_artifacts_execution_id_executions"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_artifacts_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifacts")),
        sa.UniqueConstraint(
            "content_hash", "execution_id", "kind", name=op.f("uq_artifacts_content_hash")
        ),
    )
    op.create_index(op.f("ix_artifacts_content_hash"), "artifacts", ["content_hash"])
    op.create_index(op.f("ix_artifacts_delivery_cycle_id"), "artifacts", ["delivery_cycle_id"])
    op.create_index(op.f("ix_artifacts_execution_id"), "artifacts", ["execution_id"])
    op.create_index(op.f("ix_artifacts_kind"), "artifacts", ["kind"])
    op.create_index(op.f("ix_artifacts_project_id"), "artifacts", ["project_id"])

    op.create_table(
        "checkpoints",
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("pending_ref_type", sa.String(length=64), nullable=False),
        sa.Column("pending_ref_id", sa.Uuid(), nullable=False),
        sa.Column("continuation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("runtime_checkpoint_ref", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolution", sa.String(length=32), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["executions.id"],
            name=op.f("fk_checkpoints_execution_id_executions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_checkpoints")),
    )
    op.create_index(op.f("ix_checkpoints_execution_id"), "checkpoints", ["execution_id"])

    op.create_table(
        "clarifications",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("blocking", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("answered_by_actor_id", sa.Uuid(), nullable=True),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["answered_by_actor_id"],
            ["actors.id"],
            name=op.f("fk_clarifications_answered_by_actor_id_actors"),
        ),
        sa.ForeignKeyConstraint(
            ["delivery_cycle_id"],
            ["delivery_cycles.id"],
            name=op.f("fk_clarifications_delivery_cycle_id_delivery_cycles"),
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["executions.id"],
            name=op.f("fk_clarifications_execution_id_executions"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_clarifications_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clarifications")),
    )
    op.create_index(
        op.f("ix_clarifications_delivery_cycle_id"), "clarifications", ["delivery_cycle_id"]
    )
    op.create_index(op.f("ix_clarifications_project_id"), "clarifications", ["project_id"])

    op.create_table(
        "execution_events",
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["executions.id"],
            name=op.f("fk_execution_events_execution_id_executions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_execution_events")),
        sa.UniqueConstraint("execution_id", "seq", name=op.f("uq_execution_events_execution_id")),
    )
    op.create_index(op.f("ix_execution_events_execution_id"), "execution_events", ["execution_id"])

    op.create_foreign_key(
        op.f("fk_model_calls_execution_id_executions"),
        "model_calls",
        "executions",
        ["execution_id"],
        ["id"],
    )

    op.execute(
        """
        CREATE TRIGGER trg_execution_snapshots_immutable
        BEFORE UPDATE OR DELETE ON execution_snapshots
        FOR EACH ROW EXECUTE FUNCTION olympus_forbid_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_artifacts_immutable
        BEFORE UPDATE OR DELETE ON artifacts
        FOR EACH ROW EXECUTE FUNCTION olympus_forbid_mutation();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION olympus_execution_terminal_guard() RETURNS trigger AS $$
        BEGIN
          IF OLD.status IN (
            'COMPLETED', 'FAILED', 'TIMED_OUT', 'CANCELLED', 'STALE'
          ) AND TG_OP = 'UPDATE' THEN
            IF to_jsonb(NEW) IS DISTINCT FROM to_jsonb(OLD) THEN
              RAISE EXCEPTION 'terminal execution is immutable';
            END IF;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_executions_terminal_immutable
        BEFORE UPDATE ON executions
        FOR EACH ROW EXECUTE FUNCTION olympus_execution_terminal_guard();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_executions_terminal_immutable ON executions")
    op.execute("DROP FUNCTION IF EXISTS olympus_execution_terminal_guard()")
    op.execute("DROP TRIGGER IF EXISTS trg_artifacts_immutable ON artifacts")
    op.execute("DROP TRIGGER IF EXISTS trg_execution_snapshots_immutable ON execution_snapshots")
    op.drop_constraint(
        op.f("fk_model_calls_execution_id_executions"), "model_calls", type_="foreignkey"
    )
    op.drop_table("execution_events")
    op.drop_table("clarifications")
    op.drop_table("checkpoints")
    op.drop_table("artifacts")
    op.drop_table("execution_leases")
    op.drop_constraint(
        op.f("fk_executions_snapshot_id_execution_snapshots"), "executions", type_="foreignkey"
    )
    op.drop_table("execution_snapshots")
    op.drop_index("uq_one_active_exec_per_task", table_name="executions")
    op.drop_table("executions")
