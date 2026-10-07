"""Phase 04 — execution workspaces, materializations, candidate commits, tokens

Revision ID: 0008_p04_workspaces
Revises: 0007_p04_actions
Create Date: 2026-10-02 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_p04_workspaces"
down_revision: str | None = "0007_p04_actions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "execution_workspaces",
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column(
            "workspace_type", sa.String(length=32), server_default="GIT_WORKTREE", nullable=False
        ),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("base_commit", sa.String(length=64), nullable=False),
        sa.Column("logical_location", sa.String(length=512), nullable=False),
        sa.Column("branch", sa.String(length=256), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("removed_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "logical_location !~ '(^/|^[A-Za-z]:|\\.\\.)'",
            name=op.f("ck_execution_workspaces_ck_execution_workspaces_logical"),
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["executions.id"],
            name=op.f("fk_execution_workspaces_execution_id_executions"),
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name=op.f("fk_execution_workspaces_repository_id_repositories"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_execution_workspaces")),
        sa.UniqueConstraint("execution_id", name=op.f("uq_execution_workspaces_execution_id")),
    )
    op.create_index(
        op.f("ix_execution_workspaces_repository_id"),
        "execution_workspaces",
        ["repository_id"],
    )
    op.create_index(
        "uq_execution_workspaces_logical_active",
        "execution_workspaces",
        ["logical_location"],
        unique=True,
        postgresql_where=sa.text("state IN ('CREATING','ACTIVE','RETAINED')"),
    )

    op.create_table(
        "repository_materializations",
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "action_request_ids",
            postgresql.ARRAY(sa.Uuid()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("resulting_sha", sa.String(length=64), nullable=True),
        sa.Column("observed_default_branch", sa.String(length=256), nullable=True),
        sa.Column("error_class", sa.String(length=64), nullable=True),
        sa.Column("error_detail", sa.String(length=2048), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name=op.f("fk_repository_materializations_repository_id_repositories"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repository_materializations")),
    )
    op.create_index(
        op.f("ix_repository_materializations_repository_id"),
        "repository_materializations",
        ["repository_id"],
    )

    op.create_table(
        "candidate_commits",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("branch", sa.String(length=256), nullable=False),
        sa.Column("sha", sa.String(length=64), nullable=False),
        sa.Column("parent_sha", sa.String(length=64), nullable=False),
        sa.Column("base_sha", sa.String(length=64), nullable=False),
        sa.Column("changed_files", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("diff_artifact_id", sa.Uuid(), nullable=True),
        sa.Column(
            "principal_symbols_declared",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["diff_artifact_id"],
            ["artifacts.id"],
            name=op.f("fk_candidate_commits_diff_artifact_id_artifacts"),
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["executions.id"],
            name=op.f("fk_candidate_commits_execution_id_executions"),
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name=op.f("fk_candidate_commits_repository_id_repositories"),
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_candidate_commits_task_id_tasks")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate_commits")),
        sa.UniqueConstraint("execution_id", name=op.f("uq_candidate_commits_execution_id")),
        sa.UniqueConstraint(
            "repository_id", "sha", name=op.f("uq_candidate_commits_repository_id")
        ),
    )

    op.create_table(
        "execution_tokens",
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("lease_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["executions.id"],
            name=op.f("fk_execution_tokens_execution_id_executions"),
        ),
        sa.ForeignKeyConstraint(
            ["lease_id"],
            ["execution_leases.id"],
            name=op.f("fk_execution_tokens_lease_id_execution_leases"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_execution_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_execution_tokens_token_hash")),
    )
    op.create_index(op.f("ix_execution_tokens_execution_id"), "execution_tokens", ["execution_id"])


def downgrade() -> None:
    op.drop_table("execution_tokens")
    op.drop_table("candidate_commits")
    op.drop_table("repository_materializations")
    op.drop_index("uq_execution_workspaces_logical_active", table_name="execution_workspaces")
    op.drop_table("execution_workspaces")
