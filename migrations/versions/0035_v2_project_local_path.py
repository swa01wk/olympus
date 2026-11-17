"""v2 — remember the local folder a project was started from.

Revision ID: 0035_v2_project_local_path
Revises: 0034_v2_autopilot
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0035_v2_project_local_path"
down_revision: str | None = "0034_v2_autopilot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("local_path", sa.String(length=1024), nullable=True))
    op.create_unique_constraint(op.f("uq_projects_local_path"), "projects", ["local_path"])


def downgrade() -> None:
    op.drop_constraint(op.f("uq_projects_local_path"), "projects", type_="unique")
    op.drop_column("projects", "local_path")
