from __future__ import annotations

from typing import Any

from core.commands.bus import Command, CommandBus, CommandResult
from core.commands.context import CommandContext
from sqlalchemy.ext.asyncio import AsyncSession


async def dispatch(
    session: AsyncSession,
    bus: CommandBus,
    *,
    name: str,
    target_type: str,
    target_id: str,
    payload: dict[str, Any],
    ctx: CommandContext,
) -> CommandResult:
    return await bus.dispatch(
        session,
        Command(
            name=name,
            target_type=target_type,
            target_id=target_id,
            payload=payload,
        ),
        ctx,
    )
