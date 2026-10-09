from __future__ import annotations

from unittest.mock import patch

import pytest
from core.domain.enums import TaskStatus
from core.domain.executions.models import Execution
from core.domain.tasks.models import Task
from core.execution.worker import ExecutionWorker
from core.scheduler.admission import AdmissionService
from core.state.transition_service import TransitionService
from sqlalchemy import select
from tests.fixtures.brownfield_harness import brownfield_cycle_at_code_index

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class _MissingRunner:
    async def run(self, config):  # noqa: ANN001, ANN201
        raise FileNotFoundError(2, "No such file or directory", "pytest")


async def test_executor_exception_fails_task_instead_of_crashing_worker(
    db_session, system_ctx
) -> None:
    cycle, _, _ = await brownfield_cycle_at_code_index(db_session, system_ctx)
    await TransitionService().transition(
        db_session, "delivery_cycle", cycle.id, "CODE_INDEX", "start_spec_recovery", system_ctx
    )
    await db_session.flush()

    await AdmissionService().admit_batch(db_session, 10, system_ctx)
    worker = ExecutionWorker(worker_id="crash-test")
    with patch("core.tools.handlers.test_runner.get_sandbox_runner", return_value=_MissingRunner()):
        assert await worker.run_once(db_session, system_ctx)

    task = (
        await db_session.execute(
            select(Task).where(
                Task.delivery_cycle_id == cycle.id,
                Task.title == "Run existing repository tests",
            )
        )
    ).scalar_one()
    assert task.status == TaskStatus.FAILED
    execution = (
        await db_session.execute(select(Execution).where(Execution.task_id == task.id))
    ).scalar_one()
    assert execution.failure_class == "EXECUTOR_FILENOTFOUNDERROR"
    assert "pytest" in execution.failure_detail["message"]
