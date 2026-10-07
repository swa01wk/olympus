"""Phase 15 — defects, reproduction, trace correlation, root cause.

Revision ID: 0028_p15_defects
Revises: 0027_feature_spec_supersede
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0028_p15_defects"
down_revision: str | None = "0027_feature_spec_supersede"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "defects",
        sa.Column("key", sa.String(length=16), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("product_source_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("external_ref", sa.String(length=256), nullable=True),
        sa.Column("inbound_event_id", sa.Uuid(), nullable=True),
        sa.Column("affected_release_id", sa.Uuid(), nullable=True),
        sa.Column("affected_sha", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=8), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("triage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("linked_feature_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expected_ac_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("unlinked_acknowledged", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["affected_release_id"], ["releases.id"]),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.ForeignKeyConstraint(["inbound_event_id"], ["inbound_events.id"]),
        sa.ForeignKeyConstraint(["product_source_id"], ["product_sources.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "source_type", "external_ref"),
    )
    op.create_index("ix_defects_project_id", "defects", ["project_id"])
    op.create_index("ix_defects_delivery_cycle_id", "defects", ["delivery_cycle_id"])

    op.create_table(
        "reproductions",
        sa.Column("defect_id", sa.Uuid(), nullable=False),
        sa.Column("phase", sa.String(length=32), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_hash", sa.String(length=64), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("signature_matched", sa.Boolean(), nullable=False),
        sa.Column("runs", sa.Integer(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=True),
        sa.Column("junit_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"]),
        sa.ForeignKeyConstraint(["defect_id"], ["defects.id"]),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence.id"]),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"]),
        sa.ForeignKeyConstraint(["junit_artifact_id"], ["artifacts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reproductions_defect_id", "reproductions", ["defect_id"])

    op.create_table(
        "trace_correlations",
        sa.Column("reproduction_id", sa.Uuid(), nullable=False),
        sa.Column("index_version_id", sa.Uuid(), nullable=False),
        sa.Column("entry_route_key", sa.String(length=256), nullable=True),
        sa.Column("traceback_stable_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("executed_stable_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("candidates", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["index_version_id"], ["code_index_versions.id"]),
        sa.ForeignKeyConstraint(["reproduction_id"], ["reproductions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_trace_correlations_reproduction_id", "trace_correlations", ["reproduction_id"]
    )

    op.create_table(
        "root_cause_analyses",
        sa.Column("defect_id", sa.Uuid(), nullable=False),
        sa.Column("trace_correlation_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("faulty_stable_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("knowledge_class", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("fix_outline", sa.Text(), nullable=False),
        sa.Column("regression_risks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("cited_evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("impact_assessment_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["defect_id"], ["defects.id"]),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"]),
        sa.ForeignKeyConstraint(["impact_assessment_id"], ["impact_assessments.id"]),
        sa.ForeignKeyConstraint(["trace_correlation_id"], ["trace_correlations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_root_cause_analyses_defect_id", "root_cause_analyses", ["defect_id"])

    op.create_table(
        "expected_behavior_resolutions",
        sa.Column("defect_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("resolution_kind", sa.String(length=32), nullable=False),
        sa.Column("ac_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("spec_delta_id", sa.Uuid(), nullable=True),
        sa.Column("approval_id", sa.Uuid(), nullable=True),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["approval_id"], ["approvals.id"]),
        sa.ForeignKeyConstraint(["defect_id"], ["defects.id"]),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"]),
        sa.ForeignKeyConstraint(["spec_delta_id"], ["spec_deltas.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_expected_behavior_resolutions_defect_id",
        "expected_behavior_resolutions",
        ["defect_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_expected_behavior_resolutions_defect_id", table_name="expected_behavior_resolutions"
    )
    op.drop_table("expected_behavior_resolutions")
    op.drop_index("ix_root_cause_analyses_defect_id", table_name="root_cause_analyses")
    op.drop_table("root_cause_analyses")
    op.drop_index("ix_trace_correlations_reproduction_id", table_name="trace_correlations")
    op.drop_table("trace_correlations")
    op.drop_index("ix_reproductions_defect_id", table_name="reproductions")
    op.drop_table("reproductions")
    op.drop_index("ix_defects_delivery_cycle_id", table_name="defects")
    op.drop_index("ix_defects_project_id", table_name="defects")
    op.drop_table("defects")
