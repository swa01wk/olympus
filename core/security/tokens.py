"""API token scopes, expiry, rotation and authorization."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.actors.models import Actor, ApiToken
from core.domain.actors.tokens import generate_token, hash_token
from core.domain.enums import ActorRole

ApiScope = Literal["read", "operate", "approve", "admin"]

SCOPE_ADMIN: frozenset[str] = frozenset({"admin"})
SCOPE_WEBHOOK_PREFIX = "webhook:"

DEFAULT_SCOPES: list[str] = ["read", "operate"]


def _role_default_scopes(roles: list[str]) -> frozenset[str]:
    scopes: set[str] = set()
    if "admin" in roles or "ADMIN" in roles:
        scopes.add("admin")
        scopes.update(DEFAULT_SCOPES)
        scopes.add("approve")
    elif ActorRole.OPERATOR.value in roles or "operator" in roles:
        scopes.update(DEFAULT_SCOPES)
        scopes.add("approve")
    else:
        scopes.add("read")
    return frozenset(scopes)


def token_has_scope(token_scopes: list[str], required: str) -> bool:
    if "admin" in token_scopes:
        return True
    if required.startswith(SCOPE_WEBHOOK_PREFIX):
        return required in token_scopes or f"{SCOPE_WEBHOOK_PREFIX}*" in token_scopes
    return required in token_scopes


def actor_can(required: str, actor: Actor, token_scopes: list[str] | None) -> bool:
    scopes = frozenset(token_scopes or [])
    if not scopes:
        scopes = _role_default_scopes(list(actor.roles or []))
    return token_has_scope(list(scopes), required)


async def create_api_token(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    scopes: list[str] | None = None,
    expires_at: datetime | None = None,
    rotated_from_id: uuid.UUID | None = None,
) -> tuple[str, ApiToken]:
    raw = generate_token()
    row = ApiToken(
        actor_id=actor_id,
        token_hash=hash_token(raw),
        scopes=scopes or list(DEFAULT_SCOPES),
        expires_at=expires_at,
        rotated_from_id=rotated_from_id,
    )
    session.add(row)
    await session.flush()
    return raw, row


async def rotate_api_token(
    session: AsyncSession,
    token_id: uuid.UUID,
    *,
    grace_hours: int = 24,
) -> tuple[str, ApiToken]:
    old = await session.get(ApiToken, token_id)
    if old is None or old.revoked_at is not None:
        raise ValueError("token not found or revoked")
    now = datetime.now(UTC).replace(tzinfo=None)
    raw, new_row = await create_api_token(
        session,
        actor_id=old.actor_id,
        scopes=list(old.scopes or []),
        expires_at=old.expires_at,
        rotated_from_id=old.id,
    )
    old.revoked_at = now
    await session.flush()
    return raw, new_row


async def revoke_api_token(session: AsyncSession, token_id: uuid.UUID) -> None:
    row = await session.get(ApiToken, token_id)
    if row is None:
        raise ValueError("token not found")
    row.revoked_at = datetime.now(UTC).replace(tzinfo=None)
    await session.flush()


async def resolve_token_row(session: AsyncSession, bearer: str) -> tuple[Actor, ApiToken] | None:
    digest = hash_token(bearer)
    result = await session.execute(
        select(ApiToken, Actor)
        .join(Actor, Actor.id == ApiToken.actor_id)
        .where(ApiToken.token_hash == digest, ApiToken.revoked_at.is_(None), Actor.active.is_(True))
    )
    row = result.first()
    if row is None:
        return None
    token_row, actor = row
    now = datetime.now(UTC).replace(tzinfo=None)
    if token_row.expires_at is not None and token_row.expires_at.replace(tzinfo=None) < now:
        return None
    token_row.last_used_at = now
    await session.flush()
    return actor, token_row
