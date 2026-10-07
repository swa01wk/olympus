from __future__ import annotations

import uuid
from typing import Any

import uuid6
from core.domain.audit.models import AuditEvent
from core.domain.enums import ActorKind
from core.security.audit_chain import compute_hash, next_chain_link
from sqlalchemy.ext.asyncio import AsyncSession


async def append_audit(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    actor_kind: ActorKind,
    action: str,
    target_type: str,
    target_id: str,
    correlation_id: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    command_log_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
) -> AuditEvent:
    chain_seq, prev_hash = await next_chain_link(session, project_id)
    row = AuditEvent(
        id=uuid6.uuid7(),
        actor_id=actor_id,
        actor_kind=actor_kind,
        action=action,
        target_type=target_type,
        target_id=target_id,
        before=before,
        after=after,
        correlation_id=correlation_id,
        command_log_id=command_log_id,
        project_id=project_id,
        chain_seq=chain_seq,
        prev_hash=prev_hash,
        hash="pending",
    )
    row.hash = compute_hash(row, chain_seq=chain_seq, prev_hash=prev_hash)
    session.add(row)
    await session.flush()
    return row
