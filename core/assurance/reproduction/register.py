from __future__ import annotations

from sqlalchemy import select

from core.assurance.reproduction.executor import run_regression_test, run_reproduction
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind
from core.execution.executors.base import ExecutionContext, ExecutorOutcome
from core.execution.executors.deterministic import register_deterministic_executor


async def _wrap_reproduction(ctx: ExecutionContext) -> ExecutorOutcome:
    session = ctx.session
    if session is None:
        return ExecutorOutcome(
            status="FAILED",
            error_code="NO_SESSION",
            error_message="reproduction.run requires database session",
        )
    actor = (
        await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
    ).scalar_one()
    command_ctx = CommandContext(actor=actor, correlation_id=str(ctx.execution.id))
    return await run_reproduction(session, ctx, command_ctx)


async def _wrap_regression(ctx: ExecutionContext) -> ExecutorOutcome:
    session = ctx.session
    if session is None:
        return ExecutorOutcome(
            status="FAILED",
            error_code="NO_SESSION",
            error_message="reproduction.regression requires database session",
        )
    actor = (
        await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
    ).scalar_one()
    command_ctx = CommandContext(actor=actor, correlation_id=str(ctx.execution.id))
    return await run_regression_test(session, ctx, command_ctx)


def register_reproduction_executors() -> None:
    register_deterministic_executor("reproduction.run", _wrap_reproduction)
    register_deterministic_executor("reproduction.regression", _wrap_regression)
