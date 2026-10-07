"""Phase 16 — connector configs, reconciliation, repository events, secrets, deployments

Revision ID: 0030_p16_integrations
Revises: 0029_p15_unreproduced_approval
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030_p16_integrations"
down_revision: str | None = "0029_p15_unreproduced_approval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "secrets",
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("rotated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_secrets")),
        sa.UniqueConstraint("name", name=op.f("uq_secrets_name")),
    )

    op.create_table(
        "connector_configs",
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("connector", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.String(length=2048), nullable=True),
        sa.Column("secret_ref", sa.String(length=512), nullable=True),
        sa.Column(
            "enabled_actions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("rate_limit", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_connector_configs_project_id_projects"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_connector_configs")),
    )
    op.create_index(
        "ix_connector_configs_project_connector",
        "connector_configs",
        ["project_id", "connector"],
    )

    op.create_table(
        "repository_events",
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("inbound_event_id", sa.Uuid(), nullable=True),
        sa.Column("ref", sa.String(length=512), nullable=False),
        sa.Column("before_sha", sa.String(length=64), nullable=True),
        sa.Column("after_sha", sa.String(length=64), nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["inbound_event_id"],
            ["inbound_events.id"],
            name=op.f("fk_repository_events_inbound_event_id_inbound_events"),
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name=op.f("fk_repository_events_repository_id_repositories"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repository_events")),
    )
    op.create_index("ix_repository_events_repository_id", "repository_events", ["repository_id"])

    op.create_foreign_key(
        op.f("fk_repository_revisions_repository_event_id_repository_events"),
        "repository_revisions",
        "repository_events",
        ["repository_event_id"],
        ["id"],
    )

    op.add_column(
        "repositories",
        sa.Column("last_known_head_sha", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column("webhook_external_id", sa.String(length=256), nullable=True),
    )
    op.add_column("repositories", sa.Column("last_synced_at", sa.DateTime(), nullable=True))

    op.create_table(
        "reconciliation_items",
        sa.Column("key", sa.String(length=256), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("connector_action_id", sa.Uuid(), nullable=True),
        sa.Column("repository_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("last_observation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("resolved_by_actor_id", sa.Uuid(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["connector_action_id"],
            ["connector_actions.id"],
            name=op.f("fk_reconciliation_items_connector_action_id_connector_actions"),
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name=op.f("fk_reconciliation_items_repository_id_repositories"),
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_actor_id"],
            ["actors.id"],
            name=op.f("fk_reconciliation_items_resolved_by_actor_id_actors"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reconciliation_items")),
        sa.UniqueConstraint("key", name=op.f("uq_reconciliation_items_key")),
    )
    op.create_index("ix_reconciliation_items_status", "reconciliation_items", ["status"])

    op.create_table(
        "external_links",
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_type", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=512), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_external_links")),
        sa.UniqueConstraint(
            "entity_type",
            "entity_id",
            "provider",
            "external_type",
            "external_id",
            name=op.f("uq_external_links_entity"),
        ),
    )
    op.create_index(
        "ix_external_links_entity",
        "external_links",
        ["entity_type", "entity_id"],
    )

    op.create_table(
        "deployments",
        sa.Column("release_id", sa.Uuid(), nullable=False),
        sa.Column("target", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("connector_action_id", sa.Uuid(), nullable=False),
        sa.Column("health", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["connector_action_id"],
            ["connector_actions.id"],
            name=op.f("fk_deployments_connector_action_id_connector_actions"),
        ),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["releases.id"],
            name=op.f("fk_deployments_release_id_releases"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deployments")),
    )
    op.create_index("ix_deployments_release_id", "deployments", ["release_id"])


def downgrade() -> None:
    op.drop_table("deployments")
    op.drop_table("external_links")
    op.drop_table("reconciliation_items")
    op.drop_column("repositories", "last_synced_at")
    op.drop_column("repositories", "webhook_external_id")
    op.drop_column("repositories", "last_known_head_sha")
    op.drop_constraint(
        op.f("fk_repository_revisions_repository_event_id_repository_events"),
        "repository_revisions",
        type_="foreignkey",
    )
    op.drop_table("repository_events")
    op.drop_table("connector_configs")
    op.drop_table("secrets")
