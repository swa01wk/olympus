from __future__ import annotations

from core.domain.actors.models import Actor, ApiToken
from core.security.tokens import resolve_token_row
from sqlalchemy.ext.asyncio import AsyncSession


async def resolve_actor(session: AsyncSession, token: str) -> Actor | None:
    resolved = await resolve_token_row(session, token)
    if resolved is None:
        return None
    actor, _token = resolved
    return actor


async def resolve_actor_and_token(
    session: AsyncSession, token: str
) -> tuple[Actor, ApiToken] | None:
    return await resolve_token_row(session, token)
