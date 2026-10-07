"""Phase 05 — decompositions, knowledge, scope sets

Revision ID: 0012_p05_knowledge_scope
Revises: 0011_p05_feature_specs
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_p05_knowledge_scope"
down_revision: str | None = "0011_p05_feature_specs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_decompositions",
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("product_source_version_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=True),
        sa.Column("artifact_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("validation_report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"]),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"]),
        sa.ForeignKeyConstraint(["product_source_version_id"], ["product_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column(
        "feature_specs",
        sa.Column("decomposition_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_feature_specs_decomposition_id",
        "feature_specs",
        "product_decompositions",
        ["decomposition_id"],
        ["id"],
    )

    op.create_table(
        "knowledge_items",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=True),
        sa.Column("class", sa.String(length=32), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("subject_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("blocking", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["supersedes_id"], ["knowledge_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "scope_sets",
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by_actor_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_actor_id"], ["actors.id"]),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "scope_set_items",
        sa.Column("scope_set_id", sa.Uuid(), nullable=False),
        sa.Column("feature_spec_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["feature_spec_id"], ["feature_specs.id"]),
        sa.ForeignKeyConstraint(["scope_set_id"], ["scope_sets.id"]),
        sa.PrimaryKeyConstraint("scope_set_id", "feature_spec_id"),
    )


def downgrade() -> None:
    op.drop_table("scope_set_items")
    op.drop_table("scope_sets")
    op.drop_table("knowledge_items")
    op.drop_constraint("fk_feature_specs_decomposition_id", "feature_specs", type_="foreignkey")
    op.drop_column("feature_specs", "decomposition_id")
    op.drop_table("product_decompositions")
