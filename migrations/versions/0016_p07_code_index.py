"""Phase 07 — code intelligence index

Revision ID: 0016_p07_code_index
Revises: 0015_p06_task_plans_spec_refs
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_p07_code_index"
down_revision: str | None = "0015_p06_task_plans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "code_index_versions",
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("scope_ref", sa.String(length=256), server_default="", nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("parent_index_version_id", sa.Uuid(), nullable=True),
        sa.Column("indexer_version", sa.String(length=32), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "stats", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["parent_index_version_id"], ["code_index_versions.id"]),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repository_id",
            "commit_sha",
            "kind",
            "scope_ref",
            "indexer_version",
            name="uq_code_index_versions_repo_sha_kind_scope_ver",
        ),
    )
    op.create_index(
        "ix_code_index_versions_repository_id", "code_index_versions", ["repository_id"]
    )

    op.create_table(
        "code_entities",
        sa.Column("index_version_id", sa.Uuid(), nullable=False),
        sa.Column("stable_key", sa.String(length=512), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=16), server_default="python", nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=True),
        sa.Column("qualified_name", sa.String(length=512), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=True),
        sa.Column("end_line", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("is_public", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["index_version_id"], ["code_index_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("index_version_id", "stable_key", name="uq_code_entities_version_key"),
    )
    op.create_index("ix_code_entities_index_version_id", "code_entities", ["index_version_id"])
    op.create_index("ix_code_entities_file_path", "code_entities", ["file_path"])
    op.execute(
        """
        CREATE INDEX ix_code_entities_qn_trgm ON code_entities
        USING gin (qualified_name gin_trgm_ops);
        """
    )

    op.create_table(
        "code_relations",
        sa.Column("index_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_entity_id", sa.Uuid(), nullable=False),
        sa.Column("relation", sa.String(length=32), nullable=False),
        sa.Column("target_entity_id", sa.Uuid(), nullable=False),
        sa.Column("provenance", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["source_entity_id"], ["code_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_entity_id"], ["code_entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "index_version_id",
            "source_entity_id",
            "relation",
            "target_entity_id",
            name="uq_code_relations_version_src_rel_tgt",
        ),
    )
    op.create_index("ix_code_relations_index_version_id", "code_relations", ["index_version_id"])
    op.create_index("ix_rel_src", "code_relations", ["source_entity_id", "relation"])
    op.create_index("ix_rel_tgt", "code_relations", ["target_entity_id", "relation"])

    op.execute(
        """
        CREATE OR REPLACE FUNCTION olympus_code_index_version_ready_guard() RETURNS trigger AS $$
        BEGIN
          IF OLD.status = 'READY' AND TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'ready code_index_version is immutable';
          END IF;
          IF OLD.status = 'READY' AND TG_OP = 'UPDATE' THEN
            IF NEW.status IN ('SUPERSEDED', 'DISCARDED') THEN
              IF to_jsonb(NEW) - 'status' IS DISTINCT FROM to_jsonb(OLD) - 'status' THEN
                RAISE EXCEPTION 'ready code_index_version is immutable except status supersede/discard';
              END IF;
            ELSIF to_jsonb(NEW) IS DISTINCT FROM to_jsonb(OLD) THEN
              RAISE EXCEPTION 'ready code_index_version is immutable';
            END IF;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_code_index_versions_ready_immutable
        BEFORE UPDATE OR DELETE ON code_index_versions
        FOR EACH ROW EXECUTE FUNCTION olympus_code_index_version_ready_guard();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_code_index_versions_ready_immutable ON code_index_versions"
    )
    op.execute("DROP FUNCTION IF EXISTS olympus_code_index_version_ready_guard()")
    op.drop_table("code_relations")
    op.drop_table("code_entities")
    op.drop_table("code_index_versions")
