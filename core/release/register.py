"""Register Phase 10 deterministic release executors."""

from __future__ import annotations

from core.execution.executors.base import ExecutionContext, ExecutorOutcome
from core.execution.executors.deterministic import register_deterministic_executor


def register_release_executors() -> None:
    register_deterministic_executor("stratos.release", _stratos_release_wrapper)


async def _stratos_release_wrapper(ctx: ExecutionContext) -> ExecutorOutcome:
    session = ctx.session
    if session is None:
        return ExecutorOutcome(
            status="FAILED",
            error_code="NO_SESSION",
            error_message="stratos.release requires database session",
        )
    from sqlalchemy import select

    from core.commands.context import CommandContext
    from core.domain.actors.models import Actor
    from core.domain.enums import ActorKind
    from core.release.stratos_executor import run_stratos_release

    actor = (
        await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
    ).scalar_one()
    command_ctx = CommandContext(
        actor=actor,
        correlation_id=str(ctx.execution.id),
    )
    return await run_stratos_release(session, ctx, command_ctx)
