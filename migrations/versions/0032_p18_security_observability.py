"""Phase 18 — observability, security and recovery hardening

Revision ID: 0032_p18_security_observability
Revises: 0031_p17_orchestrator
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0032_p18_security_observability"
down_revision: str | None = "0031_p17_orchestrator"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHAIN_SENTINEL = "00000000-0000-0000-0000-000000000000"


def _row_hash(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def upgrade() -> None:
    op.add_column(
        "api_tokens",
        sa.Column("scopes", postgresql.ARRAY(sa.String()), server_default="{}", nullable=False),
    )
    op.add_column("api_tokens", sa.Column("expires_at", sa.DateTime(), nullable=True))
    op.add_column("api_tokens", sa.Column("last_used_at", sa.DateTime(), nullable=True))
    op.add_column("api_tokens", sa.Column("rotated_from_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_api_tokens_rotated_from_id_api_tokens"),
        "api_tokens",
        "api_tokens",
        ["rotated_from_id"],
        ["id"],
    )

    op.add_column(
        "integration_sources",
        sa.Column("secondary_secret_ref", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "integration_sources",
        sa.Column("secondary_valid_until", sa.DateTime(), nullable=True),
    )

    op.add_column("audit_events", sa.Column("project_id", sa.Uuid(), nullable=True))
    op.add_column("audit_events", sa.Column("prev_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_events", sa.Column("hash", sa.String(length=64), nullable=True))
    op.add_column("audit_events", sa.Column("chain_seq", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f("fk_audit_events_project_id_projects"),
        "audit_events",
        "projects",
        ["project_id"],
        ["id"],
    )
    op.create_index(
        "uq_audit_events_project_chain_seq",
        "audit_events",
        ["project_id", "chain_seq"],
        unique=True,
        postgresql_where=sa.text("chain_seq IS NOT NULL"),
    )

    op.add_column(
        "domain_events",
        sa.Column("trace_context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.create_table(
        "rate_limits",
        sa.Column("key", sa.String(length=256), nullable=False),
        sa.Column("window_start", sa.DateTime(), nullable=False),
        sa.Column("count", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("key", "window_start", name=op.f("pk_rate_limits")),
    )

    op.add_column("model_calls", sa.Column("raw_prompt_ref", sa.String(length=512), nullable=True))
    op.add_column(
        "model_calls", sa.Column("raw_response_ref", sa.String(length=512), nullable=True)
    )
    op.add_column("model_calls", sa.Column("retention_expires_at", sa.DateTime(), nullable=True))

    op.add_column("execution_tokens", sa.Column("worker_id", sa.String(length=128), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT id, actor_id, actor_kind, action, target_type, target_id,
                   before, after, correlation_id, command_log_id, occurred_at, project_id
            FROM audit_events
            ORDER BY occurred_at ASC, id ASC
            """
        )
    ).fetchall()

    chains: dict[str, tuple[int, str | None]] = {}
    for row in rows:
        pid = str(row.project_id) if row.project_id else _CHAIN_SENTINEL
        seq, prev = chains.get(pid, (0, None))
        seq += 1
        payload = {
            "id": str(row.id),
            "actor_id": str(row.actor_id),
            "actor_kind": str(row.actor_kind),
            "action": row.action,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "before": row.before,
            "after": row.after,
            "correlation_id": row.correlation_id,
            "command_log_id": str(row.command_log_id) if row.command_log_id else None,
            "project_id": pid if pid != _CHAIN_SENTINEL else None,
            "chain_seq": seq,
            "prev_hash": prev,
        }
        digest = _row_hash({k: v for k, v in payload.items() if k not in {"prev_hash", "hash"}})
        if prev:
            digest = hashlib.sha256(f"{digest}|{prev}".encode()).hexdigest()
        conn.execute(
            sa.text(
                """
                UPDATE audit_events
                SET chain_seq = :seq, prev_hash = :prev, hash = :hash,
                    project_id = COALESCE(project_id, :project_id)
                WHERE id = :id
                """
            ),
            {
                "seq": seq,
                "prev": prev,
                "hash": digest,
                "project_id": None if pid == _CHAIN_SENTINEL else row.project_id,
                "id": row.id,
            },
        )
        chains[pid] = (seq, digest)

    op.alter_column("audit_events", "hash", nullable=False)
    op.alter_column("audit_events", "chain_seq", nullable=False)


def downgrade() -> None:
    op.drop_column("execution_tokens", "worker_id")
    op.drop_column("model_calls", "retention_expires_at")
    op.drop_column("model_calls", "raw_response_ref")
    op.drop_column("model_calls", "raw_prompt_ref")
    op.drop_table("rate_limits")
    op.drop_column("domain_events", "trace_context")
    op.drop_index("uq_audit_events_project_chain_seq", table_name="audit_events")
    op.drop_constraint(
        op.f("fk_audit_events_project_id_projects"), "audit_events", type_="foreignkey"
    )
    op.drop_column("audit_events", "chain_seq")
    op.drop_column("audit_events", "hash")
    op.drop_column("audit_events", "prev_hash")
    op.drop_column("audit_events", "project_id")
    op.drop_column("integration_sources", "secondary_valid_until")
    op.drop_column("integration_sources", "secondary_secret_ref")
    op.drop_constraint(
        op.f("fk_api_tokens_rotated_from_id_api_tokens"), "api_tokens", type_="foreignkey"
    )
    op.drop_column("api_tokens", "rotated_from_id")
    op.drop_column("api_tokens", "last_used_at")
    op.drop_column("api_tokens", "expires_at")
    op.drop_column("api_tokens", "scopes")
