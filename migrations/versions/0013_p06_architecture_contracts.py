"""Phase 06 — architectures and architecture_contracts

Revision ID: 0013_p06_architecture
Revises: 0012_p05_knowledge_scope
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_p06_architecture"
down_revision: str | None = "0012_p05_knowledge_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "architectures",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("lineage_key", sa.String(length=128), server_default="ARCH", nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("execution_id", sa.Uuid(), nullable=True),
        sa.Column("approval_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["approval_id"], ["approvals.id"]),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["supersedes_id"], ["architectures.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "lineage_key",
            "version",
            name="uq_architectures_project_lineage_version",
        ),
    )
    op.create_index("ix_architectures_project_id", "architectures", ["project_id"])
    op.create_index("ix_architectures_status", "architectures", ["status"])

    op.create_table(
        "architecture_contracts",
        sa.Column("architecture_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["architecture_id"], ["architectures.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("architecture_id", "key"),
    )
    op.create_index(
        "ix_architecture_contracts_architecture_id", "architecture_contracts", ["architecture_id"]
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION olympus_architecture_approved_guard() RETURNS trigger AS $$
        BEGIN
          IF OLD.status = 'APPROVED' AND TG_OP = 'UPDATE' THEN
            RAISE EXCEPTION 'approved architecture is immutable';
          END IF;
          IF OLD.status = 'APPROVED' AND TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'approved architecture is immutable';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_architectures_approved_immutable
        BEFORE UPDATE OR DELETE ON architectures
        FOR EACH ROW EXECUTE FUNCTION olympus_architecture_approved_guard();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_architectures_approved_immutable ON architectures")
    op.execute("DROP FUNCTION IF EXISTS olympus_architecture_approved_guard()")
    op.drop_table("architecture_contracts")
    op.drop_table("architectures")
