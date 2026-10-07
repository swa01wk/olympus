"""Phase 02 — model_calls audit table and runtime checkpoint schema

Revision ID: 0005_p02_model_calls
Revises: 0004_p01_events
Create Date: 2026-10-01 23:45:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_p02_model_calls"
down_revision: str | None = "0004_p01_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS langgraph_runtime")
    op.create_table(
        "model_calls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=True),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=True),
        sa.Column("agent_profile", sa.String(length=128), nullable=False),
        sa.Column("purpose", sa.String(length=256), nullable=False),
        sa.Column("alias", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt_template_id", sa.String(length=128), nullable=True),
        sa.Column("prompt_template_version", sa.String(length=32), nullable=True),
        sa.Column("prompt_hash", sa.String(length=64), nullable=False),
        sa.Column("output_schema", sa.String(length=128), nullable=True),
        sa.Column("output_schema_hash", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("latency_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "cost_usd_estimate",
            sa.Numeric(precision=12, scale=6),
            server_default="0",
            nullable=False,
        ),
        sa.Column("transport_retries", sa.Integer(), server_default="0", nullable=False),
        sa.Column("schema_retries", sa.Integer(), server_default="0", nullable=False),
        sa.Column("validation_errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("provider_request_id", sa.String(length=128), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("response_artifact_ref", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_calls")),
    )
    op.create_index("ix_model_calls_exec", "model_calls", ["execution_id", "created_at"])
    op.create_index(op.f("ix_model_calls_execution_id"), "model_calls", ["execution_id"])
    op.create_index(op.f("ix_model_calls_project_id"), "model_calls", ["project_id"])
    op.create_index(op.f("ix_model_calls_delivery_cycle_id"), "model_calls", ["delivery_cycle_id"])
    op.execute(
        """
        CREATE TRIGGER trg_model_calls_immutable
        BEFORE UPDATE OR DELETE ON model_calls
        FOR EACH ROW EXECUTE FUNCTION olympus_forbid_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_model_calls_immutable ON model_calls")
    op.drop_index(op.f("ix_model_calls_delivery_cycle_id"), table_name="model_calls")
    op.drop_index(op.f("ix_model_calls_project_id"), table_name="model_calls")
    op.drop_index(op.f("ix_model_calls_execution_id"), table_name="model_calls")
    op.drop_index("ix_model_calls_exec", table_name="model_calls")
    op.drop_table("model_calls")
    op.execute("DROP SCHEMA IF EXISTS langgraph_runtime CASCADE")
