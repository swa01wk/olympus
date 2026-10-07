"""Phase 09 — evidence, obligations, coverage, gates

Revision ID: 0019_p09_assurance
Revises: 0018_p08_traceability
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_p09_assurance"
down_revision: str | None = "0018_p08_traceability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("findings", sa.Column("fingerprint", sa.String(length=64), nullable=True))
    op.create_index("ix_findings_fingerprint", "findings", ["fingerprint"])

    op.create_table(
        "verification_obligations",
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("integration_candidate_id", sa.Uuid(), nullable=False),
        sa.Column("gate_type", sa.String(length=32), nullable=False),
        sa.Column("subject_type", sa.String(length=32), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("subject_key", sa.String(length=128), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column(
            "allowed_evidence_types",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column(
            "source_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.ForeignKeyConstraint(["integration_candidate_id"], ["integration_candidates.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "integration_candidate_id",
            "subject_type",
            "subject_id",
            "gate_type",
            name="uq_obligations_ic_subject_gate",
        ),
    )
    op.create_index(
        "ix_verification_obligations_ic",
        "verification_obligations",
        ["integration_candidate_id"],
    )

    op.create_table(
        "evidence",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("integration_candidate_id", sa.Uuid(), nullable=True),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("result", sa.String(length=16), nullable=False),
        sa.Column("subject_type", sa.String(length=32), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("obligation_id", sa.Uuid(), nullable=True),
        sa.Column("check_ref", sa.String(length=512), nullable=False),
        sa.Column("check_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("log_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("producer", sa.String(length=32), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=True),
        sa.Column("carried_forward_from_id", sa.Uuid(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["carried_forward_from_id"], ["evidence.id"]),
        sa.ForeignKeyConstraint(["check_artifact_id"], ["artifacts.id"]),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"]),
        sa.ForeignKeyConstraint(["integration_candidate_id"], ["integration_candidates.id"]),
        sa.ForeignKeyConstraint(["log_artifact_id"], ["artifacts.id"]),
        sa.ForeignKeyConstraint(["obligation_id"], ["verification_obligations.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )

    op.create_table(
        "acceptance_coverage",
        sa.Column("obligation_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("satisfied", sa.Boolean(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence.id"]),
        sa.ForeignKeyConstraint(["obligation_id"], ["verification_obligations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "gates",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("integration_candidate_id", sa.Uuid(), nullable=False),
        sa.Column("gate_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("recommendation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("inputs_hash", sa.String(length=64), nullable=True),
        sa.Column("policy_version_id", sa.Uuid(), nullable=True),
        sa.Column("finalized_at", sa.DateTime(), nullable=True),
        sa.Column("finalized_by", sa.String(length=128), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["delivery_cycle_id"], ["delivery_cycles.id"]),
        sa.ForeignKeyConstraint(["integration_candidate_id"], ["integration_candidates.id"]),
        sa.ForeignKeyConstraint(["policy_version_id"], ["policy_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
        sa.UniqueConstraint("integration_candidate_id", "gate_type"),
    )

    op.create_table(
        "verification_plans",
        sa.Column("integration_candidate_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=True),
        sa.Column("artifact_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "validation_report",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"]),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"]),
        sa.ForeignKeyConstraint(["integration_candidate_id"], ["integration_candidates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "reviews",
        sa.Column("integration_candidate_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=True),
        sa.Column("recommendation", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.String(length=4096), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"]),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"]),
        sa.ForeignKeyConstraint(["integration_candidate_id"], ["integration_candidates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION olympus_evidence_immutable() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'evidence rows are immutable';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_evidence_immutable
        BEFORE UPDATE OR DELETE ON evidence
        FOR EACH ROW EXECUTE FUNCTION olympus_evidence_immutable();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION olympus_gates_terminal_immutable() RETURNS trigger AS $$
        BEGIN
          IF OLD.status IN ('PASS','FAIL') AND NEW.status IS DISTINCT FROM OLD.status
             AND NEW.status <> 'SUPERSEDED' THEN
            RAISE EXCEPTION 'finalized gate is immutable';
          END IF;
          IF NEW.status IN ('PASS','FAIL') AND (NEW.finalized_by IS DISTINCT FROM 'SYSTEM:gate_finalizer') THEN
            RAISE EXCEPTION 'gates finalized_by must be SYSTEM:gate_finalizer';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_gates_terminal_immutable
        BEFORE UPDATE ON gates
        FOR EACH ROW EXECUTE FUNCTION olympus_gates_terminal_immutable();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_gates_terminal_immutable ON gates")
    op.execute("DROP FUNCTION IF EXISTS olympus_gates_terminal_immutable()")
    op.execute("DROP TRIGGER IF EXISTS trg_evidence_immutable ON evidence")
    op.execute("DROP FUNCTION IF EXISTS olympus_evidence_immutable()")
    op.drop_table("reviews")
    op.drop_table("verification_plans")
    op.drop_table("gates")
    op.drop_table("acceptance_coverage")
    op.drop_table("evidence")
    op.drop_table("verification_obligations")
    op.drop_index("ix_findings_fingerprint", table_name="findings")
    op.drop_column("findings", "fingerprint")
