"""Scope integration candidate and finding keys per cycle/project (not global).

Revision ID: 0021_p10_scoped_keys
Revises: 0020_p10_releases
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0021_p10_scoped_keys"
down_revision: str | None = "0020_p10_releases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_integration_candidates_key", "integration_candidates", type_="unique")
    op.create_unique_constraint(
        "uq_integration_candidates_cycle_key",
        "integration_candidates",
        ["delivery_cycle_id", "key"],
    )
    op.drop_constraint("uq_findings_key", "findings", type_="unique")
    op.create_unique_constraint(
        "uq_findings_project_key",
        "findings",
        ["project_id", "key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_findings_project_key", "findings", type_="unique")
    op.create_unique_constraint("uq_findings_key", "findings", ["key"])
    op.drop_constraint(
        "uq_integration_candidates_cycle_key", "integration_candidates", type_="unique"
    )
    op.create_unique_constraint("uq_integration_candidates_key", "integration_candidates", ["key"])
