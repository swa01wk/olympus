from __future__ import annotations

import pytest
from apps.execution_worker.main import WorkerShutdown, run_loop
from apps.scheduler_worker.main import WorkerShutdown as SchedulerShutdown


@pytest.mark.unit
def test_worker_shutdown_flag() -> None:
    shutdown = WorkerShutdown()
    assert shutdown.stop_requested is False
    shutdown.request_stop()
    assert shutdown.stop_requested is True


@pytest.mark.unit
def test_scheduler_sigterm_handler_sets_stop_flag() -> None:
    shutdown = SchedulerShutdown()
    shutdown.request_stop(15, None)
    assert shutdown.stop_requested is True


@pytest.mark.unit
async def test_worker_once_exits(migrated_db: str) -> None:
    _ = migrated_db
    code = await run_loop(once=True)
    assert code == 0
