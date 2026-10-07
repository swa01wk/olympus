"""Add UNREPRODUCED_REPAIR to approvaltype enum (Phase 15 bug-fix guard).

Revision ID: 0029_p15_unreproduced_approval
Revises: 0028_p15_defects
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0029_p15_unreproduced_approval"
down_revision: str | None = "0028_p15_defects"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE approvaltype ADD VALUE IF NOT EXISTS 'UNREPRODUCED_REPAIR'")


def downgrade() -> None:
    pass
