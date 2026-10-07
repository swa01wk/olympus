"""Scope gate and evidence keys per cycle/project (not global).

Revision ID: 0022_p10_scoped_assurance_keys
Revises: 0021_p10_scoped_keys
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0022_p10_scoped_assurance_keys"
down_revision: str | None = "0021_p10_scoped_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_gates_key", "gates", type_="unique")
    op.create_unique_constraint(
        "uq_gates_cycle_key",
        "gates",
        ["delivery_cycle_id", "key"],
    )
    op.drop_constraint("uq_evidence_key", "evidence", type_="unique")
    op.create_unique_constraint(
        "uq_evidence_project_key",
        "evidence",
        ["project_id", "key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_evidence_project_key", "evidence", type_="unique")
    op.create_unique_constraint("uq_evidence_key", "evidence", ["key"])
    op.drop_constraint("uq_gates_cycle_key", "gates", type_="unique")
    op.create_unique_constraint("uq_gates_key", "gates", ["key"])
