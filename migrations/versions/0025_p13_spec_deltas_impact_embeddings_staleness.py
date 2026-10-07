"""Phase 13 — spec deltas, impact assessments, embeddings, staleness.

Revision ID: 0025_p13_spec_deltas_impact
Revises: 0024_p12_baselines_readiness
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0025_p13_spec_deltas_impact"
down_revision: str | None = "0024_p12_baselines_readiness"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "spec_deltas",
        sa.Column("key", sa.String(length=16), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("feature_id", sa.Uuid(), nullable=False),
        sa.Column("from_spec_id", sa.Uuid(), nullable=True),
        sa.Column("to_spec_id", sa.Uuid(), nullable=False),
        sa.Column("changes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("approval_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["approval_id"], ["approvals.id"]),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.ForeignKeyConstraint(["feature_id"], ["features.id"]),
        sa.ForeignKeyConstraint(["from_spec_id"], ["feature_specs.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["to_spec_id"], ["feature_specs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "key", name="uq_spec_deltas_project_key"),
    )
    op.create_index("ix_spec_deltas_delivery_cycle_id", "spec_deltas", ["delivery_cycle_id"])

    op.create_table(
        "impact_assessments",
        sa.Column("key", sa.String(length=16), nullable=False),
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("index_version_id", sa.Uuid(), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column("seed_kind", sa.String(length=32), nullable=False),
        sa.Column("spec_delta_id", sa.Uuid(), nullable=True),
        sa.Column(
            "seed_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("architecture_delta_suggested", sa.Boolean(), nullable=False),
        sa.Column(
            "summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("policy_version_id", sa.Uuid(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.ForeignKeyConstraint(["index_version_id"], ["code_index_versions.id"]),
        sa.ForeignKeyConstraint(["policy_version_id"], ["policy_versions.id"]),
        sa.ForeignKeyConstraint(["spec_delta_id"], ["spec_deltas.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("delivery_cycle_id", "key", name="uq_ia_cycle_key"),
    )
    op.create_index(
        "ix_impact_assessments_delivery_cycle_id", "impact_assessments", ["delivery_cycle_id"]
    )

    op.create_table(
        "impact_items",
        sa.Column("impact_assessment_id", sa.Uuid(), nullable=False),
        sa.Column("item_type", sa.String(length=32), nullable=False),
        sa.Column("ref", sa.String(length=512), nullable=False),
        sa.Column("impact_kind", sa.String(length=32), nullable=False),
        sa.Column("retrieval_source", sa.String(length=32), nullable=False),
        sa.Column(
            "path",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("contract_surface", sa.Boolean(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("selected_for_verification", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["impact_assessment_id"], ["impact_assessments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_impact_items_assessment_id", "impact_items", ["impact_assessment_id"])

    op.create_table(
        "embeddings",
        sa.Column("subject_type", sa.String(length=32), nullable=False),
        sa.Column("subject_key", sa.String(length=512), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("dim", sa.Integer(), nullable=False),
        sa.Column("vector", Vector(1536), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subject_type",
            "subject_key",
            "content_hash",
            "model",
            name="uq_embeddings_subject_hash_model",
        ),
    )

    op.create_table(
        "staleness_events",
        sa.Column("subject_type", sa.String(length=32), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("cause_type", sa.String(length=64), nullable=False),
        sa.Column("cause_ref", sa.String(length=512), nullable=True),
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_staleness_events_subject",
        "staleness_events",
        ["subject_type", "subject_id"],
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_embeddings_vector_hnsw
        ON embeddings USING hnsw (vector vector_cosine_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_embeddings_vector_hnsw")
    op.drop_table("staleness_events")
    op.drop_table("embeddings")
    op.drop_table("impact_items")
    op.drop_table("impact_assessments")
    op.drop_table("spec_deltas")
