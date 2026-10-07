"""Phase 08 — canonical pointers, entity changes, spec-code links

Revision ID: 0018_p08_traceability
Revises: 0017_p08_ic_findings
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_p08_traceability"
down_revision: str | None = "0017_p08_ic_findings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "repository_index_pointers",
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_index_version_id", sa.Uuid(), nullable=True),
        sa.Column("released_index_version_id", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by_event_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["canonical_index_version_id"], ["code_index_versions.id"]),
        sa.ForeignKeyConstraint(["released_index_version_id"], ["code_index_versions.id"]),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("repository_id"),
    )

    op.create_table(
        "code_entity_changes",
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("stable_key", sa.String(length=512), nullable=False),
        sa.Column("change_kind", sa.String(length=16), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_commit_sha", sa.String(length=64), nullable=False),
        sa.Column("integration_candidate_id", sa.Uuid(), nullable=False),
        sa.Column("integrated_sha", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"]),
        sa.ForeignKeyConstraint(["integration_candidate_id"], ["integration_candidates.id"]),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_code_entity_changes_repo_stable_key",
        "code_entity_changes",
        ["repository_id", "stable_key"],
    )

    op.create_table(
        "spec_code_links",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("spec_type", sa.String(length=32), nullable=False),
        sa.Column("spec_id", sa.Uuid(), nullable=False),
        sa.Column("spec_lineage_key", sa.String(length=128), nullable=False),
        sa.Column("code_stable_key", sa.String(length=512), nullable=False),
        sa.Column("relation", sa.String(length=16), nullable=False),
        sa.Column("origin", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("execution_id", sa.Uuid(), nullable=True),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column(
            "evidence_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("established_index_version_id", sa.Uuid(), nullable=False),
        sa.Column("last_confirmed_index_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("promoted_from_link_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["established_index_version_id"], ["code_index_versions.id"]),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"]),
        sa.ForeignKeyConstraint(["last_confirmed_index_version_id"], ["code_index_versions.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["promoted_from_link_id"], ["spec_code_links.id"]),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scl_spec", "spec_code_links", ["spec_lineage_key", "status"])
    op.create_index(
        "ix_scl_code", "spec_code_links", ["repository_id", "code_stable_key", "status"]
    )

    op.execute(
        """
        ALTER TABLE spec_code_links ADD CONSTRAINT ck_scl_generated_lineage_refs
        CHECK (
          origin <> 'GENERATED_LINEAGE'
          OR (task_id IS NOT NULL AND execution_id IS NOT NULL AND commit_sha IS NOT NULL)
        );
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE spec_code_links DROP CONSTRAINT IF EXISTS ck_scl_generated_lineage_refs"
    )
    op.drop_index("ix_scl_code", table_name="spec_code_links")
    op.drop_index("ix_scl_spec", table_name="spec_code_links")
    op.drop_table("spec_code_links")
    op.drop_index("ix_code_entity_changes_repo_stable_key", table_name="code_entity_changes")
    op.drop_table("code_entity_changes")
    op.drop_table("repository_index_pointers")
