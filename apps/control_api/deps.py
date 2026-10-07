from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import cast

from core.commands.bus import CommandBus
from core.commands.context import CommandContext
from core.domain.actors.models import Actor, ApiToken
from core.domain.exceptions import DomainError
from core.observability.correlation import get_correlation_id
from core.security.route_scopes import required_scope
from core.security.tokens import actor_can
from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.control_api.auth import resolve_actor_and_token


def get_command_bus(request: Request) -> CommandBus:
    return cast(CommandBus, request.app.state.command_bus)


async def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return cast(async_sessionmaker[AsyncSession], request.app.state.session_factory)


async def get_db(
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session, session.begin():
        yield session


async def get_actor_and_token(
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: AsyncSession = Depends(get_db),
) -> tuple[Actor, ApiToken | None]:
    if not authorization or not authorization.startswith("Bearer "):
        raise DomainError(code="UNAUTHENTICATED", message="Bearer token required")
    token = authorization.removeprefix("Bearer ").strip()
    resolved = await resolve_actor_and_token(session, token)
    if resolved is None:
        raise DomainError(code="UNAUTHENTICATED", message="Invalid or revoked token")
    actor, api_token = resolved
    return actor, api_token


async def get_actor(
    auth: tuple[Actor, ApiToken | None] = Depends(get_actor_and_token),
) -> Actor:
    actor, _token = auth
    return actor


def require_scope(scope: str) -> Callable[..., Awaitable[Actor]]:
    async def _dep(
        auth: tuple[Actor, ApiToken | None] = Depends(get_actor_and_token),
    ) -> Actor:
        actor, api_token = auth
        scopes = list(api_token.scopes) if api_token is not None else None
        if not actor_can(scope, actor, scopes):
            raise DomainError(code="FORBIDDEN", message=f"Scope {scope} required")
        return actor

    return cast(Callable[..., Awaitable[Actor]], _dep)


def command_context(
    request: Request,
    auth: tuple[Actor, ApiToken | None] = Depends(get_actor_and_token),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> CommandContext:
    actor, api_token = auth
    need = required_scope(request)
    scopes = list(api_token.scopes) if api_token is not None else None
    if not actor_can(need, actor, scopes):
        raise DomainError(code="FORBIDDEN", message=f"Scope {need} required")
    return CommandContext(
        actor=actor,
        correlation_id=get_correlation_id() or "unknown",
        idempotency_key=idempotency_key,
    )
