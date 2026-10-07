"""Phase 08 — integration candidates and findings

Revision ID: 0017_p08_ic_findings
Revises: 0016_p07_code_index
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_p08_ic_findings"
down_revision: str | None = "0016_p07_code_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_candidates",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("base_sha", sa.String(length=64), nullable=False),
        sa.Column("integration_branch", sa.String(length=256), nullable=False),
        sa.Column("integrated_sha", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "ordering",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("integration_execution_id", sa.Uuid(), nullable=True),
        sa.Column("checks_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("canonical_index_version_id", sa.Uuid(), nullable=True),
        sa.Column("canonical_revision_id", sa.Uuid(), nullable=True),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["canonical_revision_id"], ["repository_revisions.id"]),
        sa.ForeignKeyConstraint(["checks_artifact_id"], ["artifacts.id"]),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.ForeignKeyConstraint(["integration_execution_id"], ["executions.id"]),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.ForeignKeyConstraint(["supersedes_id"], ["integration_candidates.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index(
        "ix_integration_candidates_delivery_cycle_id",
        "integration_candidates",
        ["delivery_cycle_id"],
    )
    op.create_index(
        "ix_integration_candidates_repository_id",
        "integration_candidates",
        ["repository_id"],
    )

    op.create_table(
        "integration_candidate_commits",
        sa.Column("integration_candidate_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_commit_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("included", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("skip_reason", sa.String(length=256), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_commit_id"], ["candidate_commits.id"]),
        sa.ForeignKeyConstraint(["integration_candidate_id"], ["integration_candidates.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "integration_candidate_id",
            "candidate_commit_id",
            name="uq_ic_commits_ic_candidate",
        ),
    )

    op.create_table(
        "findings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("integration_candidate_id", sa.Uuid(), nullable=True),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("blocking", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "code_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "spec_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("remediation_task_id", sa.Uuid(), nullable=True),
        sa.Column("waiver_approval_id", sa.Uuid(), nullable=True),
        sa.Column("resolved_by_ic_id", sa.Uuid(), nullable=True),
        sa.Column("producer_execution_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.ForeignKeyConstraint(["integration_candidate_id"], ["integration_candidates.id"]),
        sa.ForeignKeyConstraint(["producer_execution_id"], ["executions.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["remediation_task_id"], ["tasks.id"]),
        sa.ForeignKeyConstraint(["resolved_by_ic_id"], ["integration_candidates.id"]),
        sa.ForeignKeyConstraint(["waiver_approval_id"], ["approvals.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_findings_delivery_cycle_id", "findings", ["delivery_cycle_id"])

    op.create_foreign_key(
        "fk_repository_revisions_integration_candidate_id",
        "repository_revisions",
        "integration_candidates",
        ["integration_candidate_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_repository_revisions_canonical_index_version_id",
        "repository_revisions",
        "code_index_versions",
        ["canonical_index_version_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_integration_candidates_canonical_index_version_id",
        "integration_candidates",
        "code_index_versions",
        ["canonical_index_version_id"],
        ["id"],
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION olympus_ic_integrated_sha_immutable() RETURNS trigger AS $$
        BEGIN
          IF OLD.integrated_sha IS NOT NULL AND NEW.integrated_sha IS DISTINCT FROM OLD.integrated_sha THEN
            RAISE EXCEPTION 'integration_candidates.integrated_sha is immutable';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_integration_candidates_integrated_sha_immutable
        BEFORE UPDATE ON integration_candidates
        FOR EACH ROW EXECUTE FUNCTION olympus_ic_integrated_sha_immutable();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_integration_candidates_integrated_sha_immutable "
        "ON integration_candidates"
    )
    op.execute("DROP FUNCTION IF EXISTS olympus_ic_integrated_sha_immutable()")
    op.drop_constraint(
        "fk_integration_candidates_canonical_index_version_id",
        "integration_candidates",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_repository_revisions_canonical_index_version_id",
        "repository_revisions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_repository_revisions_integration_candidate_id",
        "repository_revisions",
        type_="foreignkey",
    )
    op.drop_index("ix_findings_delivery_cycle_id", table_name="findings")
    op.drop_table("findings")
    op.drop_table("integration_candidate_commits")
    op.drop_index("ix_integration_candidates_repository_id", table_name="integration_candidates")
    op.drop_index(
        "ix_integration_candidates_delivery_cycle_id", table_name="integration_candidates"
    )
    op.drop_table("integration_candidates")
