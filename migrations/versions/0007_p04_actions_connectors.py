"""Phase 04 — action_requests, action_results, connector_actions, connector_results

Revision ID: 0007_p04_actions
Revises: 0006_p03_executions
Create Date: 2026-10-02 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_p04_actions"
down_revision: str | None = "0006_p03_executions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "action_requests",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=True),
        sa.Column("lease_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("agent_profile", sa.String(length=128), nullable=True),
        sa.Column("tool", sa.String(length=128), nullable=False),
        sa.Column("resource", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("params_hash", sa.String(length=64), nullable=False),
        sa.Column("task_contract_id", sa.Uuid(), nullable=True),
        sa.Column("task_contract_version", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=256), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("policy_decision", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("approval_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["actors.id"], name=op.f("fk_action_requests_actor_id_actors")
        ),
        sa.ForeignKeyConstraint(
            ["approval_id"],
            ["approvals.id"],
            name=op.f("fk_action_requests_approval_id_approvals"),
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["executions.id"],
            name=op.f("fk_action_requests_execution_id_executions"),
        ),
        sa.ForeignKeyConstraint(
            ["task_contract_id"],
            ["task_contracts.id"],
            name=op.f("fk_action_requests_task_contract_id_task_contracts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_action_requests")),
    )
    op.create_index(op.f("ix_action_requests_execution_id"), "action_requests", ["execution_id"])
    op.create_index(op.f("ix_action_requests_key"), "action_requests", ["key"])
    op.create_index(
        "ix_action_requests_execution_created",
        "action_requests",
        ["execution_id", "created_at"],
    )

    op.create_table(
        "action_results",
        sa.Column("action_request_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output_ref", sa.String(length=512), nullable=True),
        sa.Column("error_class", sa.String(length=64), nullable=True),
        sa.Column("error_detail", sa.String(length=2048), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("connector_action_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["action_request_id"],
            ["action_requests.id"],
            name=op.f("fk_action_results_action_request_id_action_requests"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_action_results")),
        sa.UniqueConstraint("action_request_id", name=op.f("uq_action_results_action_request_id")),
    )

    op.create_table(
        "connector_actions",
        sa.Column("connector", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("action_request_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=True),
        sa.Column("task_contract_ref", sa.String(length=128), nullable=True),
        sa.Column("target_resource", sa.String(length=512), nullable=False),
        sa.Column("inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("policy_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expected_result_schema", sa.String(length=128), nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("external_ref", sa.String(length=512), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["action_request_id"],
            ["action_requests.id"],
            name=op.f("fk_connector_actions_action_request_id_action_requests"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_connector_actions")),
        sa.UniqueConstraint(
            "connector", "idempotency_key", name=op.f("uq_connector_actions_connector")
        ),
    )

    op.create_table(
        "connector_results",
        sa.Column("connector_action_id", sa.Uuid(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("normalized_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_ref", sa.String(length=512), nullable=True),
        sa.Column("external_ref", sa.String(length=512), nullable=True),
        sa.Column("error_class", sa.String(length=64), nullable=True),
        sa.Column("received_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["connector_action_id"],
            ["connector_actions.id"],
            name=op.f("fk_connector_results_connector_action_id_connector_actions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_connector_results")),
    )
    op.create_index(
        op.f("ix_connector_results_connector_action_id"),
        "connector_results",
        ["connector_action_id"],
    )


def downgrade() -> None:
    op.drop_table("connector_results")
    op.drop_table("connector_actions")
    op.drop_table("action_results")
    op.drop_index("ix_action_requests_execution_created", table_name="action_requests")
    op.drop_table("action_requests")
