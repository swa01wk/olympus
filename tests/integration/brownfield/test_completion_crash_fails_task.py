from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from core.domain.enums import ExecutionStatus, LeaseState, TaskStatus
from core.domain.executions.models import Execution, ExecutionLease
from core.domain.tasks.models import Task
from core.execution.worker import ExecutionWorker
from core.scheduler.admission import AdmissionService
from core.state.transition_service import TransitionService
from sqlalchemy import select, text
from tests.fixtures.brownfield_harness import brownfield_cycle_at_code_index

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class _PassingRunner:
    async def run(self, config):  # noqa: ANN001, ANN201
        return SimpleNamespace(returncode=0, stdout="", stderr="", timed_out=False)


async def _poisoning_handler(self, session, execution, output, ctx):  # noqa: ANN001, ANN202
    await session.execute(text("SELECT 1/0"))


async def test_completion_handler_db_error_fails_execution_once(db_session, system_ctx) -> None:
    cycle, _, _ = await brownfield_cycle_at_code_index(db_session, system_ctx)
    await TransitionService().transition(
        db_session, "delivery_cycle", cycle.id, "CODE_INDEX", "start_spec_recovery", system_ctx
    )
    await db_session.flush()
    await AdmissionService().admit_batch(db_session, 10, system_ctx)

    task = (
        await db_session.execute(
            select(Task).where(
                Task.delivery_cycle_id == cycle.id,
                Task.title == "Run existing repository tests",
            )
        )
    ).scalar_one()
    task_id = task.id
    # Only the existing-tests execution may be claimed by this worker.
    other = (
        await db_session.execute(
            select(Execution).where(
                Execution.delivery_cycle_id == cycle.id,
                Execution.task_id != task_id,
                Execution.status == ExecutionStatus.QUEUED,
            )
        )
    ).scalars()
    for row in other:
        row.status = ExecutionStatus.STALE
    await db_session.flush()

    worker = ExecutionWorker(worker_id="completion-crash-test")
    with (
        patch(
            "core.tools.handlers.test_runner.get_sandbox_runner",
            return_value=_PassingRunner(),
        ),
        patch(
            "core.intelligence.recovered_specs.completion.BrownfieldCompletionService.after_existing_tests",
            _poisoning_handler,
        ),
    ):
        assert await worker.run_once(db_session, system_ctx)
        assert not await worker.run_once(db_session, system_ctx)

    task = await db_session.get(Task, task_id, populate_existing=True)
    assert task is not None
    assert task.status == TaskStatus.FAILED
    executions = (
        (await db_session.execute(select(Execution).where(Execution.task_id == task_id)))
        .scalars()
        .all()
    )
    assert len(executions) == 1
    execution = executions[0]
    assert execution.status == ExecutionStatus.FAILED
    assert execution.failure_class == "WORKER_DATAERROR"
    assert "division by zero" in execution.failure_detail["message"]
    assert execution.retriable is False
    leases = (
        (
            await db_session.execute(
                select(ExecutionLease).where(ExecutionLease.execution_id == execution.id)
            )
        )
        .scalars()
        .all()
    )
    assert leases
    assert all(lease.state != LeaseState.ACTIVE for lease in leases)
