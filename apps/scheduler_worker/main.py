from __future__ import annotations

import argparse
import asyncio
import signal
from typing import Any

from core.config.settings import get_settings
from core.observability.logging import configure_logging, get_logger


class WorkerShutdown:
    def __init__(self) -> None:
        self.stop_requested = False

    def request_stop(self, *_args: Any) -> None:
        self.stop_requested = True


async def run_tick(logger: Any) -> None:
    logger.info("scheduler_worker.tick", status="noop")


async def run_loop(*, once: bool = False) -> int:
    settings = get_settings()
    configure_logging(settings)
    logger = get_logger("apps.scheduler_worker")
    shutdown = WorkerShutdown()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown.request_stop)

    logger.info("scheduler_worker.start")
    while not shutdown.stop_requested:
        await run_tick(logger)
        if once:
            break
        await asyncio.sleep(settings.worker_poll_interval_seconds)

    logger.info("scheduler_worker.stop")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Olympus scheduler worker")
    parser.add_argument("--once", action="store_true", help="Run a single tick and exit")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run_loop(once=args.once)))


if __name__ == "__main__":
    main()
