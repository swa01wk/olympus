"""Phase 00 baseline: pg extensions and langgraph_runtime schema.

Revision ID: 0000_p00_baseline
Revises:
Create Date: 2026-10-01

Extensions are intentionally left in place on downgrade because they may be shared
by other databases on the same PostgreSQL instance.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0000_p00_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE SCHEMA IF NOT EXISTS langgraph_runtime")


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS langgraph_runtime CASCADE")
