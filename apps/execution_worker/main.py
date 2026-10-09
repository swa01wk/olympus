from __future__ import annotations

import argparse
import asyncio
import os
import signal
import uuid
from typing import Any

import core.domain.registry  # noqa: F401  # every mapper must be registered before first use
from core.commands.context import CommandContext
from core.config.settings import get_settings
from core.db.engine import create_async_engine_from_settings, dispose_engine
from core.db.session import create_session_factory, reset_session_factory
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind, ActorRole
from core.execution.worker import ExecutionWorker
from core.observability.logging import configure_logging, get_logger
from core.observability.otel import configure_otel
from core.ops.startup_reconcilers import run_startup_reconcilers
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class WorkerShutdown:
    def __init__(self) -> None:
        self.stop_requested = False

    def request_stop(self, *_args: Any) -> None:
        self.stop_requested = True


async def _system_ctx(session_factory: async_sessionmaker[AsyncSession]) -> CommandContext:
    async with session_factory() as session:
        result = await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
        actor = result.scalar_one_or_none()
        if actor is None:
            actor = Actor(
                kind=ActorKind.SYSTEM, name="execution-worker", roles=[ActorRole.SYSTEM.value]
            )
            session.add(actor)
            await session.commit()
        else:
            await session.commit()
        return CommandContext(actor=actor, correlation_id=str(uuid.uuid4()))


async def run_tick(
    logger: Any,
    session_factory: async_sessionmaker[AsyncSession],
    worker: ExecutionWorker,
    ctx: CommandContext,
) -> None:
    try:
        async with session_factory() as session, session.begin():
            ran = await worker.run_once(session, ctx)
    except Exception:
        logger.exception("execution_worker.tick_failed")
        return
    logger.info("execution_worker.tick", ran=ran)


async def run_loop(*, once: bool = False) -> int:
    settings = get_settings()
    configure_logging(settings)
    configure_otel(settings)
    logger = get_logger("apps.execution_worker")
    shutdown = WorkerShutdown()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown.request_stop)

    create_async_engine_from_settings(settings)
    session_factory = create_session_factory()
    ctx = await _system_ctx(session_factory)
    async with session_factory() as session, session.begin():
        await run_startup_reconcilers(session)
    worker_id = os.environ.get("OLYMPUS_WORKER_ID", f"execution-{uuid.uuid4().hex[:8]}")
    worker = ExecutionWorker(worker_id=worker_id)

    logger.info("execution_worker.start", worker_id=worker_id)
    while not shutdown.stop_requested:
        await run_tick(logger, session_factory, worker, ctx)
        if once:
            break
        await asyncio.sleep(settings.worker_poll_interval_seconds)

    await dispose_engine()
    reset_session_factory()
    logger.info("execution_worker.stop")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Olympus execution worker")
    parser.add_argument("--once", action="store_true", help="Run a single tick and exit")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run_loop(once=args.once)))


if __name__ == "__main__":
    main()
