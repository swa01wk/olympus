"""Tamper-evident per-project audit hash chain."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.audit.models import AuditEvent

_CHAIN_SENTINEL = uuid.UUID(int=0)


@dataclass(frozen=True)
class ChainVerification:
    project_id: uuid.UUID | None
    valid: bool
    rows_checked: int
    first_invalid_seq: int | None
    message: str


def _canonical_row(row: AuditEvent, *, chain_seq: int, prev_hash: str | None) -> dict[str, Any]:
    pid = row.project_id
    return {
        "id": str(row.id),
        "actor_id": str(row.actor_id),
        "actor_kind": row.actor_kind.value if hasattr(row.actor_kind, "value") else row.actor_kind,
        "action": row.action,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "before": row.before,
        "after": row.after,
        "correlation_id": row.correlation_id,
        "command_log_id": str(row.command_log_id) if row.command_log_id else None,
        "project_id": str(pid) if pid else None,
        "chain_seq": chain_seq,
        "prev_hash": prev_hash,
    }


def compute_hash(row: AuditEvent, *, chain_seq: int, prev_hash: str | None) -> str:
    payload = _canonical_row(row, chain_seq=chain_seq, prev_hash=prev_hash)
    payload.pop("prev_hash", None)
    base = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    if prev_hash:
        return hashlib.sha256(f"{base}|{prev_hash}".encode()).hexdigest()
    return base


async def next_chain_link(
    session: AsyncSession,
    project_id: uuid.UUID | None,
) -> tuple[int, str | None]:
    """Returns (next_seq, prev_hash) under advisory lock for the project chain."""
    from sqlalchemy import text

    lock_key = project_id or _CHAIN_SENTINEL
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": str(lock_key)},
    )
    stmt = select(AuditEvent)
    if project_id is None:
        stmt = stmt.where(AuditEvent.project_id.is_(None))
    else:
        stmt = stmt.where(AuditEvent.project_id == project_id)
    stmt = stmt.order_by(AuditEvent.chain_seq.desc()).limit(1)
    result = await session.execute(stmt)
    last = result.scalar_one_or_none()
    if last is None:
        return 1, None
    return int(last.chain_seq) + 1, last.hash


async def verify_project_chain(
    session: AsyncSession,
    project_id: uuid.UUID | None,
) -> ChainVerification:
    stmt = select(AuditEvent)
    if project_id is None:
        stmt = stmt.where(AuditEvent.project_id.is_(None))
    else:
        stmt = stmt.where(AuditEvent.project_id == project_id)
    stmt = stmt.order_by(AuditEvent.chain_seq.asc())
    result = await session.execute(stmt)
    rows = list(result.scalars())
    prev: str | None = None
    expected_seq = 1
    for row in rows:
        if row.chain_seq != expected_seq:
            return ChainVerification(
                project_id=project_id,
                valid=False,
                rows_checked=expected_seq - 1,
                first_invalid_seq=row.chain_seq,
                message=f"chain_seq gap: expected {expected_seq}, got {row.chain_seq}",
            )
        if row.prev_hash != prev:
            return ChainVerification(
                project_id=project_id,
                valid=False,
                rows_checked=expected_seq - 1,
                first_invalid_seq=row.chain_seq,
                message="prev_hash mismatch",
            )
        digest = compute_hash(row, chain_seq=row.chain_seq, prev_hash=prev)
        if digest != row.hash:
            return ChainVerification(
                project_id=project_id,
                valid=False,
                rows_checked=expected_seq - 1,
                first_invalid_seq=row.chain_seq,
                message="hash mismatch",
            )
        prev = row.hash
        expected_seq += 1
    return ChainVerification(
        project_id=project_id,
        valid=True,
        rows_checked=len(rows),
        first_invalid_seq=None,
        message="ok",
    )
