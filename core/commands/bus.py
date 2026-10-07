"""Command dispatch registry with idempotent command_log persistence and correlation."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.command_log import begin_command, complete_command, reject_command
from core.commands.context import CommandContext
from core.domain.exceptions import DomainError
from core.domain.policy.models import CommandLog

CommandHandler = Callable[
    [AsyncSession, CommandContext, dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]
]


@dataclass
class Command:
    name: str
    target_type: str
    target_id: str
    payload: dict[str, Any]


@dataclass
class CommandResult:
    ok: bool
    data: dict[str, Any]
    replayed: bool = False


class CommandBus:
    def __init__(self) -> None:
        self._handlers: dict[str, CommandHandler] = {}

    def register(self, name: str, handler: CommandHandler) -> None:
        self._handlers[name] = handler

    async def dispatch(
        self,
        session: AsyncSession,
        cmd: Command,
        ctx: CommandContext,
    ) -> CommandResult:
        handler = self._handlers.get(cmd.name)
        if handler is None:
            raise ValueError(f"Unknown command: {cmd.name}")
        log: CommandLog | None = await begin_command(
            session,
            command_name=cmd.name,
            target_type=cmd.target_type,
            target_id=cmd.target_id,
            actor_id=ctx.actor.id,
            idempotency_key=ctx.idempotency_key,
            request_body=cmd.payload,
            correlation_id=ctx.correlation_id,
        )
        if log is not None and log.result is not None:
            return CommandResult(ok=True, data=log.result, replayed=True)
        if log is not None:
            ctx = CommandContext(
                actor=ctx.actor,
                correlation_id=ctx.correlation_id,
                idempotency_key=ctx.idempotency_key,
                command_log_id=log.id,
            )
        try:
            data = await handler(session, ctx, cmd.payload)
            if log is not None:
                await complete_command(session, log, data)
            return CommandResult(ok=True, data=data)
        except DomainError as exc:
            if log is not None:
                await reject_command(
                    session,
                    log,
                    {"code": exc.code, "message": exc.message, "details": exc.details},
                )
            raise
