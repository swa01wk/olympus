"""Phase 11 — discovery, observed behaviors, recovery proposals.

Revision ID: 0023_p11_discovery_observed_behaviors_recovery
Revises: 0022_p10_scoped_assurance_keys
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023_p11_brownfield_recovery"
down_revision: str | None = "0022_p10_scoped_assurance_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("feature_specs", sa.Column("confidence", sa.String(length=16), nullable=True))
    op.add_column(
        "feature_specs", sa.Column("claimed_confidence", sa.String(length=16), nullable=True)
    )
    op.add_column("feature_specs", sa.Column("uncertainty_count", sa.Integer(), nullable=True))

    op.create_table(
        "repository_discoveries",
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "delivery_cycle_id",
            "commit_sha",
            name="uq_repository_discoveries_cycle_sha",
        ),
    )
    op.create_index(
        "ix_repository_discoveries_delivery_cycle_id",
        "repository_discoveries",
        ["delivery_cycle_id"],
    )

    op.create_table(
        "observed_behaviors",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("index_version_id", sa.Uuid(), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=2048), nullable=False),
        sa.Column("subject_stable_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provenance", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("fact_item_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.ForeignKeyConstraint(["fact_item_id"], ["knowledge_items.id"]),
        sa.ForeignKeyConstraint(["index_version_id"], ["code_index_versions.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("delivery_cycle_id", "key", name="uq_observed_behaviors_cycle_key"),
    )
    op.create_index(
        "ix_observed_behaviors_delivery_cycle_id", "observed_behaviors", ["delivery_cycle_id"]
    )

    op.create_table(
        "recovery_proposals",
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("survey_execution_id", sa.Uuid(), nullable=False),
        sa.Column(
            "feature_execution_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("validation_report", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("context_manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("reconciliation_report_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.ForeignKeyConstraint(["reconciliation_report_artifact_id"], ["artifacts.id"]),
        sa.ForeignKeyConstraint(["survey_execution_id"], ["executions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "recovered_spec_evidence",
        sa.Column("feature_spec_id", sa.Uuid(), nullable=False),
        sa.Column("element_type", sa.String(length=32), nullable=False),
        sa.Column("element_key", sa.String(length=128), nullable=False),
        sa.Column("support_type", sa.String(length=32), nullable=False),
        sa.Column("support_ref", sa.String(length=512), nullable=False),
        sa.Column("strength", sa.String(length=16), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["feature_spec_id"], ["feature_specs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("recovered_spec_evidence")
    op.drop_table("recovery_proposals")
    op.drop_index("ix_observed_behaviors_delivery_cycle_id", table_name="observed_behaviors")
    op.drop_table("observed_behaviors")
    op.drop_index(
        "ix_repository_discoveries_delivery_cycle_id", table_name="repository_discoveries"
    )
    op.drop_table("repository_discoveries")
    op.drop_column("feature_specs", "uncertainty_count")
    op.drop_column("feature_specs", "claimed_confidence")
    op.drop_column("feature_specs", "confidence")
