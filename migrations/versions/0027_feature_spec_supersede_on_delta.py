"""Allow APPROVED FeatureSpec to transition to SUPERSEDED on spec delta approval.

Revision ID: 0027_feature_spec_supersede
Revises: 0026_p14_change_requests
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0027_feature_spec_supersede"
down_revision: str | None = "0026_p14_change_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION olympus_feature_spec_approved_guard() RETURNS trigger AS $$
        BEGIN
          IF OLD.status = 'APPROVED' AND TG_OP = 'UPDATE' THEN
            IF NEW.status = 'SUPERSEDED'
               AND NEW.body IS NOT DISTINCT FROM OLD.body
               AND NEW.content_hash IS NOT DISTINCT FROM OLD.content_hash THEN
              RETURN NEW;
            END IF;
            RAISE EXCEPTION 'approved feature_spec is immutable';
          END IF;
          IF OLD.status = 'APPROVED' AND TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'approved feature_spec is immutable';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION olympus_feature_spec_approved_guard() RETURNS trigger AS $$
        BEGIN
          IF OLD.status = 'APPROVED' AND TG_OP = 'UPDATE' THEN
            RAISE EXCEPTION 'approved feature_spec is immutable';
          END IF;
          IF OLD.status = 'APPROVED' AND TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'approved feature_spec is immutable';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
