"""Phase 06 — implementation_specs

Revision ID: 0014_p06_implementation_specs
Revises: 0013_p06_architecture
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_p06_implementation_specs"
down_revision: str | None = "0013_p06_architecture"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "implementation_specs",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("lineage_key", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("feature_spec_id", sa.Uuid(), nullable=False),
        sa.Column("architecture_id", sa.Uuid(), nullable=False),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("execution_id", sa.Uuid(), nullable=True),
        sa.Column("approval_id", sa.Uuid(), nullable=True),
        sa.Column(
            "conformance_report",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["approval_id"], ["approvals.id"]),
        sa.ForeignKeyConstraint(["architecture_id"], ["architectures.id"]),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"]),
        sa.ForeignKeyConstraint(["feature_spec_id"], ["feature_specs.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["supersedes_id"], ["implementation_specs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "lineage_key",
            "version",
            name="uq_implementation_specs_project_lineage_version",
        ),
    )
    op.create_index("ix_implementation_specs_project_id", "implementation_specs", ["project_id"])
    op.create_index("ix_implementation_specs_status", "implementation_specs", ["status"])

    op.execute(
        """
        CREATE OR REPLACE FUNCTION olympus_implementation_spec_approved_guard() RETURNS trigger AS $$
        BEGIN
          IF OLD.status = 'APPROVED' AND TG_OP = 'UPDATE' THEN
            RAISE EXCEPTION 'approved implementation_spec is immutable';
          END IF;
          IF OLD.status = 'APPROVED' AND TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'approved implementation_spec is immutable';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_implementation_specs_approved_immutable
        BEFORE UPDATE OR DELETE ON implementation_specs
        FOR EACH ROW EXECUTE FUNCTION olympus_implementation_spec_approved_guard();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_implementation_specs_approved_immutable ON implementation_specs"
    )
    op.execute("DROP FUNCTION IF EXISTS olympus_implementation_spec_approved_guard()")
    op.drop_table("implementation_specs")
