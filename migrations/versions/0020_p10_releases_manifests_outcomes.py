"""Phase 10 — releases, manifests, eligibility, outcomes

Revision ID: 0020_p10_releases
Revises: 0019_p09_assurance
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_p10_releases"
down_revision: str | None = "0019_p09_assurance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "release_eligibility_evaluations",
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("integration_candidate_id", sa.Uuid(), nullable=True),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column(
            "conditions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("policy_version_id", sa.Uuid(), nullable=False),
        sa.Column("trigger_event_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.ForeignKeyConstraint(["integration_candidate_id"], ["integration_candidates.id"]),
        sa.ForeignKeyConstraint(["policy_version_id"], ["policy_versions.id"]),
        sa.ForeignKeyConstraint(["trigger_event_id"], ["domain_events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_release_eligibility_evaluations_cycle",
        "release_eligibility_evaluations",
        ["delivery_cycle_id"],
    )

    op.create_table(
        "releases",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("integration_candidate_id", sa.Uuid(), nullable=False),
        sa.Column("integrated_sha", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("manifest_id", sa.Uuid(), nullable=True),
        sa.Column("approval_id", sa.Uuid(), nullable=True),
        sa.Column("release_execution_id", sa.Uuid(), nullable=True),
        sa.Column("tag", sa.String(length=256), nullable=True),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.Column("latest_eligibility_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["approval_id"], ["approvals.id"]),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.ForeignKeyConstraint(["integration_candidate_id"], ["integration_candidates.id"]),
        sa.ForeignKeyConstraint(["latest_eligibility_id"], ["release_eligibility_evaluations.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["release_execution_id"], ["executions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "key"),
    )
    op.create_index("ix_releases_delivery_cycle_id", "releases", ["delivery_cycle_id"])

    op.create_table(
        "release_manifests",
        sa.Column("release_id", sa.Uuid(), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["release_id"], ["releases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_release_manifests_release_id", "release_manifests", ["release_id"])

    op.create_foreign_key(
        "fk_releases_manifest_id",
        "releases",
        "release_manifests",
        ["manifest_id"],
        ["id"],
    )

    op.create_table(
        "delivery_outcomes",
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("delivery_cycle_id"),
    )

    for table in (
        "release_manifests",
        "release_eligibility_evaluations",
        "delivery_outcomes",
    ):
        op.execute(
            f"""
            CREATE OR REPLACE FUNCTION olympus_{table}_immutable() RETURNS trigger AS $$
            BEGIN
              RAISE EXCEPTION '{table} rows are immutable';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_immutable
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION olympus_{table}_immutable();
            """
        )


def downgrade() -> None:
    for table in (
        "delivery_outcomes",
        "release_eligibility_evaluations",
        "release_manifests",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable ON {table}")
        op.execute(f"DROP FUNCTION IF EXISTS olympus_{table}_immutable()")
    op.drop_table("delivery_outcomes")
    op.drop_constraint("fk_releases_manifest_id", "releases", type_="foreignkey")
    op.drop_table("release_manifests")
    op.drop_table("releases")
    op.drop_table("release_eligibility_evaluations")
