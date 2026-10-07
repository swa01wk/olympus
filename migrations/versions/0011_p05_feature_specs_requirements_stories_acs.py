"""Phase 05 — feature specs and child rows

Revision ID: 0011_p05_feature_specs
Revises: 0010_p05_product_sources
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_p05_feature_specs"
down_revision: str | None = "0010_p05_product_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feature_specs",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("feature_id", sa.Uuid(), nullable=False),
        sa.Column("lineage_key", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("spec_kind", sa.String(length=32), server_default="CANONICAL", nullable=False),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("derived_from_source_version_id", sa.Uuid(), nullable=True),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("promoted_from_id", sa.Uuid(), nullable=True),
        sa.Column("approval_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["approval_id"], ["approvals.id"]),
        sa.ForeignKeyConstraint(["derived_from_source_version_id"], ["product_sources.id"]),
        sa.ForeignKeyConstraint(["feature_id"], ["features.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["supersedes_id"], ["feature_specs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "lineage_key",
            "version",
            name="uq_feature_specs_project_lineage_version",
        ),
    )

    op.create_table(
        "requirements",
        sa.Column("feature_spec_id", sa.Uuid(), nullable=False),
        sa.Column("lineage_key", sa.String(length=64), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("locked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["feature_spec_id"], ["feature_specs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feature_spec_id", "lineage_key"),
    )

    op.create_table(
        "user_stories",
        sa.Column("feature_spec_id", sa.Uuid(), nullable=False),
        sa.Column("lineage_key", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=256), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("benefit", sa.Text(), nullable=False),
        sa.Column("locked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["feature_spec_id"], ["feature_specs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feature_spec_id", "lineage_key"),
    )

    op.create_table(
        "acceptance_criteria",
        sa.Column("feature_spec_id", sa.Uuid(), nullable=False),
        sa.Column("lineage_key", sa.String(length=64), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("given", sa.Text(), nullable=True),
        sa.Column("when", sa.Text(), nullable=True),
        sa.Column("then", sa.Text(), nullable=True),
        sa.Column("mandatory", sa.Boolean(), nullable=False),
        sa.Column("evidence_requirement", sa.String(length=32), nullable=False),
        sa.Column("requirement_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("change_kind", sa.String(length=32), nullable=True),
        sa.Column("locked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["feature_spec_id"], ["feature_specs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feature_spec_id", "lineage_key"),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION olympus_feature_spec_approved_guard() RETURNS trigger AS $$
        BEGIN
          IF OLD.status = 'APPROVED' AND TG_OP = 'UPDATE' THEN
            RAISE EXCEPTION 'approved feature_spec is immutable';
          END IF;
          IF OLD.status = 'APPROVED' AND TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'approved feature_spec is immutable';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_feature_specs_approved_immutable
        BEFORE UPDATE OR DELETE ON feature_specs
        FOR EACH ROW EXECUTE FUNCTION olympus_feature_spec_approved_guard();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION olympus_locked_child_guard() RETURNS trigger AS $$
        BEGIN
          IF OLD.locked IS TRUE AND TG_OP = 'UPDATE' THEN
            RAISE EXCEPTION 'locked child row is immutable';
          END IF;
          IF OLD.locked IS TRUE AND TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'locked child row is immutable';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in ("requirements", "user_stories", "acceptance_criteria"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_locked_immutable
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION olympus_locked_child_guard();
            """
        )


def downgrade() -> None:
    for table in ("acceptance_criteria", "user_stories", "requirements"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_locked_immutable ON {table}")
    op.execute("DROP TRIGGER IF EXISTS trg_feature_specs_approved_immutable ON feature_specs")
    op.execute("DROP FUNCTION IF EXISTS olympus_locked_child_guard()")
    op.execute("DROP FUNCTION IF EXISTS olympus_feature_spec_approved_guard()")
    op.drop_table("acceptance_criteria")
    op.drop_table("user_stories")
    op.drop_table("requirements")
    op.drop_table("feature_specs")
