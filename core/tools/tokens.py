"""Run-scoped execution tokens for ToolGateway."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.domain.enums import ExecutionStatus, LeaseState
from core.domain.execution_tokens.models import ExecutionToken
from core.domain.executions.models import Execution, ExecutionLease


class TokenValidationError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _normalize_expires(expires_at: datetime) -> datetime:
    if expires_at.tzinfo is None:
        return expires_at.replace(tzinfo=UTC)
    return expires_at.astimezone(UTC)


def _sign(
    execution_id: uuid.UUID,
    lease_id: uuid.UUID,
    worker_id: str | None,
    expires_at: datetime,
    secret: str,
) -> str:
    exp = _normalize_expires(expires_at)
    worker = worker_id or ""
    payload = f"{execution_id}|{lease_id}|{worker}|{int(exp.timestamp())}"
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def issue_token(
    execution_id: uuid.UUID,
    lease_id: uuid.UUID,
    expires_at: datetime,
    *,
    worker_id: str | None = None,
) -> tuple[str, str]:
    settings = get_settings()
    secret = settings.olympus_secret_key.get_secret_value() or "dev-insecure-token-secret"
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    sig = _sign(execution_id, lease_id, worker_id, expires_at, secret)
    return f"{raw}.{sig}", token_hash


async def persist_token(
    session: AsyncSession,
    execution_id: uuid.UUID,
    lease_id: uuid.UUID,
    token_hash: str,
    expires_at: datetime,
    *,
    worker_id: str | None = None,
) -> ExecutionToken:
    row = ExecutionToken(
        execution_id=execution_id,
        lease_id=lease_id,
        token_hash=token_hash,
        expires_at=expires_at,
        worker_id=worker_id,
    )
    session.add(row)
    await session.flush()
    return row


async def validate_token(
    session: AsyncSession,
    token: str,
    *,
    execution_id: uuid.UUID | None = None,
    worker_id: str | None = None,
) -> tuple[Execution, ExecutionLease]:
    if "." not in token:
        raise TokenValidationError("malformed token")
    raw, sig = token.rsplit(".", 1)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    result = await session.execute(
        select(ExecutionToken).where(ExecutionToken.token_hash == token_hash)
    )
    row = result.scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        raise TokenValidationError("token not found or revoked")
    if execution_id is not None and row.execution_id != execution_id:
        raise TokenValidationError("token execution mismatch")
    if worker_id is not None and row.worker_id and row.worker_id != worker_id:
        raise TokenValidationError("token worker mismatch")
    now = datetime.now(UTC)
    expires = _normalize_expires(row.expires_at)
    if expires < now:
        raise TokenValidationError("token expired")
    lease = await session.get(ExecutionLease, row.lease_id)
    execution = await session.get(Execution, row.execution_id)
    if lease is None or execution is None:
        raise TokenValidationError("execution or lease missing")
    if lease.state != LeaseState.ACTIVE:
        raise TokenValidationError("lease not active")
    if execution.status not in {ExecutionStatus.STARTED, ExecutionStatus.CHECKPOINTED}:
        if execution.status in {
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.COMMITTED,
        }:
            raise TokenValidationError("token replay after completion")
        raise TokenValidationError("execution not in runnable state")
    settings = get_settings()
    secret = settings.olympus_secret_key.get_secret_value() or "dev-insecure-token-secret"
    expected = _sign(row.execution_id, row.lease_id, row.worker_id, expires, secret)
    if not hmac.compare_digest(sig, expected):
        raise TokenValidationError("invalid token signature")
    return execution, lease


async def revoke_tokens_for_execution(session: AsyncSession, execution_id: uuid.UUID) -> None:
    result = await session.execute(
        select(ExecutionToken).where(ExecutionToken.execution_id == execution_id)
    )
    now = datetime.now(UTC)
    for row in result.scalars():
        row.revoked_at = now
    await session.flush()


def default_token_expiry(lease: ExecutionLease) -> datetime:
    return lease.expires_at
