"""Warden review, Sentinel plan and Sentinel execute complete through ExecutionWorker."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from agents.warden.schemas import WardenReview
from core.assurance.enums import GateStatus, GateType, VerificationPlanStatus
from core.assurance.models import Gate, VerificationPlanRow
from core.assurance.orchestrator import AssuranceOrchestrator
from core.domain.artifacts.models import Artifact
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import TaskStatus
from core.domain.executions.models import Execution
from core.domain.tasks.models import Task
from core.runtime.providers.fake_provider import FakeProvider, FakeScriptStep
from core.scheduler.admission import AdmissionService
from sqlalchemy import select
from tests.fixtures.assurance_harness import ready_ic_with_sentinel_evidence, run_worker_rounds

pytestmark = [pytest.mark.integration, pytest.mark.git, pytest.mark.asyncio]


async def _tasks(db_session, cycle_id, prefix: str) -> list[Task]:
    return list(
        (
            await db_session.execute(
                select(Task).where(
                    Task.delivery_cycle_id == cycle_id, Task.title.startswith(prefix)
                )
            )
        ).scalars()
    )


async def _gate(db_session, ic_id, gate_type: GateType) -> Gate:
    return (
        await db_session.execute(
            select(Gate).where(Gate.integration_candidate_id == ic_id, Gate.gate_type == gate_type)
        )
    ).scalar_one()


async def _drain(db_session, ctx, fake: FakeProvider) -> None:
    providers = {"anthropic": fake, "openai": fake, "fake": fake}
    with patch("core.runtime.model_router.build_providers", side_effect=lambda **_: providers):
        await AdmissionService().admit_batch(db_session, 10, ctx)
        await run_worker_rounds(db_session, ctx, max_rounds=5)


async def test_assurance_tasks_complete_and_finalize_only_their_gate(
    db_session, system_ctx
) -> None:
    ic, _, fixture = await ready_ic_with_sentinel_evidence(
        db_session, system_ctx, project_key="p9-agents", passing=True
    )
    assert ic is not None
    cycle = await db_session.get(DeliveryCycle, fixture.cycle.id)
    assert cycle is not None

    execute_tasks = await _tasks(db_session, cycle.id, "Sentinel execute")
    assert [t.status for t in execute_tasks] == [TaskStatus.COMPLETED]
    assert (await _gate(db_session, ic.id, GateType.SENTINEL)).status == GateStatus.PASS
    assert (await _gate(db_session, ic.id, GateType.WARDEN)).status == GateStatus.PENDING
    assert (await _gate(db_session, ic.id, GateType.INTEGRATION)).status == GateStatus.PENDING

    review = WardenReview(findings=[], recommendation="APPROVE", conformance=[], summary="ok")
    fake = FakeProvider()
    fake.set_script([FakeScriptStep(structured=review.model_dump(mode="json"))])
    await AssuranceOrchestrator()._schedule_warden(db_session, ic, cycle, system_ctx)
    await _drain(db_session, system_ctx, fake)

    (warden_task,) = await _tasks(db_session, cycle.id, "Warden review")
    assert warden_task.status == TaskStatus.COMPLETED
    warden_exec = (
        await db_session.execute(select(Execution).where(Execution.task_id == warden_task.id))
    ).scalar_one()
    artifacts = (
        await db_session.execute(
            select(Artifact).where(
                Artifact.execution_id == warden_exec.id, Artifact.kind == "WARDEN_REVIEW"
            )
        )
    ).all()
    assert len(artifacts) == 1
    assert (await _gate(db_session, ic.id, GateType.WARDEN)).status == GateStatus.PASS
    assert (await _gate(db_session, ic.id, GateType.INTEGRATION)).status == GateStatus.PENDING

    adopted = (
        await db_session.execute(
            select(VerificationPlanRow).where(
                VerificationPlanRow.integration_candidate_id == ic.id,
                VerificationPlanRow.status == VerificationPlanStatus.VALIDATED,
            )
        )
    ).scalar_one()
    fake.set_script([FakeScriptStep(structured=adopted.validation_report["plan"])])
    await AssuranceOrchestrator()._schedule_sentinel_plan(db_session, ic, cycle, system_ctx)
    await _drain(db_session, system_ctx, fake)

    (plan_task,) = await _tasks(db_session, cycle.id, "Sentinel plan")
    assert plan_task.status == TaskStatus.COMPLETED
    statuses = sorted(
        r.status.value
        for r in (
            await db_session.execute(
                select(VerificationPlanRow).where(
                    VerificationPlanRow.integration_candidate_id == ic.id
                )
            )
        ).scalars()
    )
    assert statuses == ["PROPOSED", "VALIDATED"]
    assert len(await _tasks(db_session, cycle.id, "Sentinel execute")) == 1
