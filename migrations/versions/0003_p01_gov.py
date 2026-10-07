"""Phase 01 — policy, command log, audit, approvals

Revision ID: 0003_p01_gov
Revises: 0002_p01_tasks
Create Date: 2026-10-01 22:31:30.947777

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_p01_gov"
down_revision: str | None = "0002_p01_tasks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policy_versions",
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policy_versions")),
        sa.UniqueConstraint("content_hash", name=op.f("uq_policy_versions_content_hash")),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column(
            "actor_kind",
            postgresql.ENUM(
                "HUMAN",
                "AGENT",
                "SYSTEM",
                "INTEGRATION",
                name="actorkind",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("command_log_id", sa.Uuid(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["actors.id"], name=op.f("fk_audit_events_actor_id_actors")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_table(
        "command_log",
        sa.Column("command_name", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status", sa.Enum("ACCEPTED", "REJECTED", name="commandlogstatus"), nullable=False
        ),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["actors.id"], name=op.f("fk_command_log_actor_id_actors")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_command_log")),
        sa.UniqueConstraint("actor_id", "idempotency_key", name=op.f("uq_command_log_actor_id")),
    )
    op.create_table(
        "approvals",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=True),
        sa.Column(
            "approval_type",
            sa.Enum(
                "SCOPE",
                "ARCHITECTURE",
                "ARCHITECTURE_DELTA",
                "IMPLEMENTATION_SPEC",
                "SPEC_DELTA",
                "SPEC_DECISION",
                "REPAIR_SPEC",
                "PROMOTION",
                "FINDING_WAIVER",
                "ACTION",
                "RELEASE",
                "READINESS",
                name="approvaltype",
            ),
            nullable=False,
        ),
        sa.Column("subject_type", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("subject_version", sa.Integer(), nullable=False),
        sa.Column("subject_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "APPROVED",
                "REJECTED",
                "CHANGES_REQUESTED",
                "EXPIRED",
                "CANCELLED",
                name="approvalstatus",
            ),
            nullable=False,
        ),
        sa.Column("requested_by_actor_id", sa.Uuid(), nullable=False),
        sa.Column("decided_by_actor_id", sa.Uuid(), nullable=True),
        sa.Column("decision_note", sa.String(length=4096), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("policy_version_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["decided_by_actor_id"],
            ["actors.id"],
            name=op.f("fk_approvals_decided_by_actor_id_actors"),
        ),
        sa.ForeignKeyConstraint(
            ["delivery_cycle_id"],
            ["delivery_cycles.id"],
            name=op.f("fk_approvals_delivery_cycle_id_delivery_cycles"),
        ),
        sa.ForeignKeyConstraint(
            ["policy_version_id"],
            ["policy_versions.id"],
            name=op.f("fk_approvals_policy_version_id_policy_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_approvals_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_actor_id"],
            ["actors.id"],
            name=op.f("fk_approvals_requested_by_actor_id_actors"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approvals")),
        sa.UniqueConstraint("project_id", "key", name=op.f("uq_approvals_project_id")),
    )
    op.create_index(op.f("ix_approvals_project_id"), "approvals", ["project_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_approvals_project_id"), table_name="approvals")
    op.drop_table("approvals")
    op.drop_table("command_log")
    op.drop_table("audit_events")
    op.drop_table("policy_versions")
    for enum_name in ("approvalstatus", "approvaltype", "commandlogstatus"):
        op.execute(f'DROP TYPE IF EXISTS "{enum_name}" CASCADE')
