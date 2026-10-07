from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.canonical_json import sha256_hex
from core.domain.enums import CommandLogStatus
from core.domain.exceptions import IdempotencyConflict
from core.domain.policy.models import CommandLog


async def begin_command(
    session: AsyncSession,
    *,
    command_name: str,
    target_type: str,
    target_id: str,
    actor_id: uuid.UUID,
    idempotency_key: str | None,
    request_body: dict[str, Any],
    correlation_id: str,
) -> CommandLog | None:
    if not idempotency_key:
        return None
    request_hash = sha256_hex(request_body)
    existing = await session.execute(
        select(CommandLog).where(
            CommandLog.actor_id == actor_id,
            CommandLog.idempotency_key == idempotency_key,
        )
    )
    row = existing.scalar_one_or_none()
    if row is not None:
        if row.request_hash != request_hash:
            raise IdempotencyConflict()
        return row
    log = CommandLog(
        command_name=command_name,
        target_type=target_type,
        target_id=target_id,
        actor_id=actor_id,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        status=CommandLogStatus.ACCEPTED,
        correlation_id=correlation_id,
    )
    session.add(log)
    await session.flush()
    return log


async def complete_command(session: AsyncSession, log: CommandLog, result: dict[str, Any]) -> None:
    log.result = result
    log.status = CommandLogStatus.ACCEPTED
    await session.flush()


async def reject_command(session: AsyncSession, log: CommandLog, error: dict[str, Any]) -> None:
    log.error = error
    log.status = CommandLogStatus.REJECTED
    await session.flush()
