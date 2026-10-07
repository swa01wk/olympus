"""Phase 01 — domain events, revisions, triggers, view

Revision ID: 0004_p01_events
Revises: 0003_p01_gov
Create Date: 2026-10-01 22:31:30.947777

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_p01_events"
down_revision: str | None = "0003_p01_gov"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "domain_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("causation_id", sa.String(length=128), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["actors.id"], name=op.f("fk_domain_events_actor_id_actors")
        ),
        sa.ForeignKeyConstraint(
            ["delivery_cycle_id"],
            ["delivery_cycles.id"],
            name=op.f("fk_domain_events_delivery_cycle_id_delivery_cycles"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_domain_events_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_domain_events")),
        sa.UniqueConstraint("sequence", name=op.f("uq_domain_events_sequence")),
    )
    op.create_index(
        "ix_domain_events_delivery_cycle",
        "domain_events",
        ["delivery_cycle_id", "sequence"],
        unique=False,
    )
    op.create_table(
        "repository_revisions",
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column(
            "cause",
            sa.Enum(
                "MATERIALIZED",
                "INTEGRATION_READY",
                "RELEASED",
                "EXTERNAL_SYNC",
                "REVERTED",
                name="revisioncause",
            ),
            nullable=False,
        ),
        sa.Column("integration_candidate_id", sa.Uuid(), nullable=True),
        sa.Column("release_id", sa.Uuid(), nullable=True),
        sa.Column("repository_event_id", sa.Uuid(), nullable=True),
        sa.Column("reverts_revision_id", sa.Uuid(), nullable=True),
        sa.Column("canonical_index_version_id", sa.Uuid(), nullable=True),
        sa.Column("delivery_cycle_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["actors.id"], name=op.f("fk_repository_revisions_actor_id_actors")
        ),
        sa.ForeignKeyConstraint(
            ["delivery_cycle_id"],
            ["delivery_cycles.id"],
            name=op.f("fk_repository_revisions_delivery_cycle_id_delivery_cycles"),
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name=op.f("fk_repository_revisions_repository_id_repositories"),
        ),
        sa.ForeignKeyConstraint(
            ["reverts_revision_id"],
            ["repository_revisions.id"],
            name=op.f("fk_repository_revisions_reverts_revision_id_repository_revisions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repository_revisions")),
        sa.UniqueConstraint(
            "repository_id", "sequence", name=op.f("uq_repository_revisions_repository_id")
        ),
    )
    op.create_index(
        op.f("ix_repository_revisions_repository_id"),
        "repository_revisions",
        ["repository_id"],
        unique=False,
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW delivery_cycle_events AS
        SELECT id, sequence, aggregate_type, aggregate_id, project_id,
               delivery_cycle_id, event_type, payload, correlation_id,
               causation_id, actor_id, occurred_at, published_at
        FROM domain_events
        WHERE delivery_cycle_id IS NOT NULL
        ORDER BY sequence
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION olympus_forbid_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'mutation forbidden on %', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION olympus_repository_revision_guard() RETURNS trigger AS $$
        DECLARE
          latest_sha text;
          latest_cause text;
        BEGIN
          IF OLD.registered_sha IS NOT NULL AND NEW.registered_sha IS DISTINCT FROM OLD.registered_sha THEN
            RAISE EXCEPTION 'registered_sha is immutable';
          END IF;
          IF NEW.canonical_commit IS DISTINCT FROM OLD.canonical_commit THEN
            SELECT commit_sha, cause INTO latest_sha, latest_cause
            FROM repository_revisions
            WHERE repository_id = NEW.id
            ORDER BY sequence DESC
            LIMIT 1;
            IF latest_sha IS NULL OR latest_sha <> NEW.canonical_commit THEN
              RAISE EXCEPTION 'canonical_commit requires matching revision row';
            END IF;
          END IF;
          IF NEW.released_commit IS DISTINCT FROM OLD.released_commit THEN
            SELECT commit_sha, cause INTO latest_sha, latest_cause
            FROM repository_revisions
            WHERE repository_id = NEW.id
            ORDER BY sequence DESC
            LIMIT 1;
            IF latest_cause <> 'RELEASED' OR latest_sha <> NEW.released_commit THEN
              RAISE EXCEPTION 'released_commit requires RELEASED revision row';
            END IF;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in ("audit_events", "policy_versions", "repository_revisions"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_immutable
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION olympus_forbid_mutation();
            """
        )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION olympus_domain_events_publish_only() RETURNS trigger AS $$
        BEGIN
          IF to_jsonb(NEW) - 'published_at' IS DISTINCT FROM to_jsonb(OLD) - 'published_at' THEN
            RAISE EXCEPTION 'domain_events immutable except published_at';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_domain_events_publish_only
        BEFORE UPDATE ON domain_events
        FOR EACH ROW EXECUTE FUNCTION olympus_domain_events_publish_only();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_repositories_revision_guard
        BEFORE UPDATE ON repositories
        FOR EACH ROW EXECUTE FUNCTION olympus_repository_revision_guard();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION olympus_task_contract_issued_guard() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'DELETE' AND OLD.status = 'ISSUED' THEN
            RAISE EXCEPTION 'issued contract cannot be deleted';
          END IF;
          IF TG_OP = 'UPDATE' AND OLD.status = 'ISSUED' THEN
            IF NEW.status = 'SUPERSEDED' AND NEW.body IS NOT DISTINCT FROM OLD.body
               AND NEW.content_hash IS NOT DISTINCT FROM OLD.content_hash THEN
              RETURN NEW;
            END IF;
            RAISE EXCEPTION 'issued contract is immutable';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_task_contracts_immutable
        BEFORE UPDATE OR DELETE ON task_contracts
        FOR EACH ROW EXECUTE FUNCTION olympus_task_contract_issued_guard();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_task_contracts_immutable ON task_contracts")
    op.execute("DROP FUNCTION IF EXISTS olympus_task_contract_issued_guard()")
    op.execute("DROP TRIGGER IF EXISTS trg_repositories_revision_guard ON repositories")
    op.execute("DROP TRIGGER IF EXISTS trg_domain_events_publish_only ON domain_events")
    op.execute("DROP FUNCTION IF EXISTS olympus_domain_events_publish_only()")
    for table in ("repository_revisions", "policy_versions", "audit_events"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable ON {table}")
    op.execute("DROP FUNCTION IF EXISTS olympus_repository_revision_guard()")
    op.execute("DROP FUNCTION IF EXISTS olympus_forbid_mutation()")
    op.execute("DROP VIEW IF EXISTS delivery_cycle_events")
    op.drop_index(op.f("ix_repository_revisions_repository_id"), table_name="repository_revisions")
    op.drop_table("repository_revisions")
    op.drop_index("ix_domain_events_delivery_cycle", table_name="domain_events")
    op.drop_table("domain_events")
    op.execute('DROP TYPE IF EXISTS "revisioncause" CASCADE')
