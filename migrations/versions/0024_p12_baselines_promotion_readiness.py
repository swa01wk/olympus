"""Phase 12 — behavioral baselines, promotion, readiness.

Revision ID: 0024_p12_baselines_readiness
Revises: 0023_p11_brownfield_recovery
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024_p12_baselines_readiness"
down_revision: str | None = "0023_p11_brownfield_recovery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "behavioral_baselines",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("lineage_key", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("given", sa.Text(), nullable=False),
        sa.Column("when", sa.Text(), nullable=False),
        sa.Column("then", sa.Text(), nullable=False),
        sa.Column("check_kind", sa.String(length=32), nullable=False),
        sa.Column("check_ref", sa.String(length=512), nullable=False),
        sa.Column("check_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("feature_spec_id", sa.Uuid(), nullable=True),
        sa.Column("ac_lineage_key", sa.String(length=64), nullable=True),
        sa.Column(
            "observed_behavior_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "exercised_stable_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("established_sha", sa.String(length=64), nullable=False),
        sa.Column("established_evidence_id", sa.Uuid(), nullable=True),
        sa.Column("activation", sa.String(length=32), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["check_artifact_id"], ["artifacts.id"]),
        sa.ForeignKeyConstraint(["established_evidence_id"], ["evidence.id"]),
        sa.ForeignKeyConstraint(["feature_spec_id"], ["feature_specs.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "lineage_key", "version", name="uq_baselines_lineage_ver"
        ),
    )
    op.create_index("ix_behavioral_baselines_project_id", "behavioral_baselines", ["project_id"])
    op.create_index("ix_behavioral_baselines_status", "behavioral_baselines", ["status"])

    op.create_table(
        "baseline_sets",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=16), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "key", name="uq_baseline_sets_project_key"),
    )

    op.create_table(
        "baseline_set_items",
        sa.Column("baseline_set_id", sa.Uuid(), nullable=False),
        sa.Column("baseline_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["baseline_id"], ["behavioral_baselines.id"]),
        sa.ForeignKeyConstraint(["baseline_set_id"], ["baseline_sets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("baseline_set_id", "baseline_id", name="uq_baseline_set_items"),
    )

    op.add_column(
        "projects",
        sa.Column("active_baseline_set_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_projects_active_baseline_set_id",
        "projects",
        "baseline_sets",
        ["active_baseline_set_id"],
        ["id"],
    )

    op.create_table(
        "promotion_decisions",
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("subject_type", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=64), nullable=False),
        sa.Column("approval_id", sa.Uuid(), nullable=True),
        sa.Column("decided_by_actor_id", sa.Uuid(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "result_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["approval_id"], ["approvals.id"]),
        sa.ForeignKeyConstraint(["decided_by_actor_id"], ["actors.id"]),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "delivery_cycle_id",
            "subject_type",
            "subject_id",
            name="uq_promotion_decisions_cycle_subject",
        ),
    )
    op.create_index(
        "ix_promotion_decisions_delivery_cycle_id",
        "promotion_decisions",
        ["delivery_cycle_id"],
    )

    op.create_table(
        "readiness_assessments",
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column("index_version_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_revision_id", sa.Uuid(), nullable=False),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("remediable", sa.Boolean(), nullable=False),
        sa.Column(
            "reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("policy_version_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["canonical_revision_id"], ["repository_revisions.id"]),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.ForeignKeyConstraint(["index_version_id"], ["code_index_versions.id"]),
        sa.ForeignKeyConstraint(["policy_version_id"], ["policy_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_readiness_assessments_delivery_cycle_id",
        "readiness_assessments",
        ["delivery_cycle_id"],
    )

    op.create_check_constraint(
        "ck_evidence_ic_or_baseline_subject",
        "evidence",
        "integration_candidate_id IS NOT NULL OR subject_type IN ('BASELINE', 'DEFECT')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_evidence_ic_or_baseline_subject", "evidence", type_="check")
    op.drop_index("ix_readiness_assessments_delivery_cycle_id", table_name="readiness_assessments")
    op.drop_table("readiness_assessments")
    op.drop_index("ix_promotion_decisions_delivery_cycle_id", table_name="promotion_decisions")
    op.drop_table("promotion_decisions")
    op.drop_constraint("fk_projects_active_baseline_set_id", "projects", type_="foreignkey")
    op.drop_table("baseline_set_items")
    op.drop_table("baseline_sets")
    op.drop_index("ix_behavioral_baselines_status", table_name="behavioral_baselines")
    op.drop_index("ix_behavioral_baselines_project_id", table_name="behavioral_baselines")
    op.drop_table("behavioral_baselines")
    op.drop_column("projects", "active_baseline_set_id")
