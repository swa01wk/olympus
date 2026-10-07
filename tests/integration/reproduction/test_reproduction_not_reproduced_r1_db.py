"""PRE_REPAIR on fixed supportdesk_r1 must not count as REPRODUCED (plan §12)."""

from __future__ import annotations

import uuid

import pytest
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.exceptions import DomainError
from core.domain.tasks.models import Task
from core.product_model.defects.orchestrator import BugFixOrchestrator
from core.product_model.defects.service import DefectService
from sqlalchemy import select
from tests.fixtures.code_index_harness import SUPPORTDESK_R1
from tests.journey.bug_fix_helpers import (
    REPRO_TEST_SOURCE,
    _ensure_reproduction_run_ready,
    maybe_apply_triage_fallback,
)
from tests.journey.seed import TRUSTED_SEED, seed_trusted_project

REPRO_PATH = "tests/olympus_repro/test_closed_ticket_500.py"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pre_repair_not_reproduced_on_supportdesk_r1(
    db_session, system_ctx: CommandContext
) -> None:
    trusted = await seed_trusted_project(db_session, SUPPORTDESK_R1, TRUSTED_SEED, system_ctx)
    defect = await DefectService().intake(
        db_session,
        project_id=trusted.project_id,
        title="False positive repro",
        description="PATCH on CLOSED ticket returns 500",
        source_type="test",
        external_ref="not-repro-r1",
        inbound_event_id=None,
        ctx=system_ctx,
    )
    assert defect.delivery_cycle_id is not None
    cycle_id = defect.delivery_cycle_id
    await maybe_apply_triage_fallback(db_session, cycle_id, system_ctx)
    cycle = await db_session.get(DeliveryCycle, cycle_id)
    assert cycle is not None
    if cycle.state == "TRIAGE":
        await DeliveryCycleService().run_command(
            db_session, cycle_id, "start_reproduction", "TRIAGE", system_ctx
        )
    from core.execution.artifacts import ArtifactStore

    store = ArtifactStore()
    art = await store.put(
        db_session,
        project_id=cycle.project_id,
        delivery_cycle_id=cycle.id,
        execution_id=None,
        kind="REPRODUCTION_TEST",
        schema_name="reproduction_test",
        schema_version="1",
        content={"relative_path": REPRO_PATH, "test_source": REPRO_TEST_SOURCE},
        created_by_actor_id=system_ctx.actor.id,
    )
    await BugFixOrchestrator().schedule_reproduction_run(db_session, cycle_id, art.id, system_ctx)
    await _ensure_reproduction_run_ready(db_session, cycle_id, system_ctx)

    from core.assurance.reproduction.register import _wrap_reproduction
    from core.domain.executions.models import Execution
    from core.domain.task_contracts.models import TaskContract
    from core.domain.task_contracts.schemas import parse_task_contract_body
    from core.execution.executors.base import ExecutionContext
    from core.execution.snapshots.builder import SnapshotBuilder
    from core.scheduler.admission import AdmissionService

    task = (
        await db_session.execute(
            select(Task).where(
                Task.delivery_cycle_id == cycle_id,
                Task.title == "Run reproduction test",
            )
        )
    ).scalar_one()
    try:
        execution = await AdmissionService().admit_task(db_session, task.id, system_ctx)
    except DomainError as exc:
        raise AssertionError(str(exc.message)) from exc
    execution = await db_session.get(Execution, execution.id)
    assert execution is not None
    contract_row = await db_session.get(TaskContract, execution.task_contract_id)
    assert contract_row is not None
    contract = parse_task_contract_body(contract_row.body)
    snapshot = await SnapshotBuilder().build(db_session, execution)
    exec_ctx = ExecutionContext(
        execution=execution,
        snapshot=snapshot,
        contract=contract,
        lease_id=uuid.uuid4(),
        worker_id="not-repro-r1",
        contract_payload=contract_row.body if isinstance(contract_row.body, dict) else {},
        session=db_session,
    )
    outcome = await _wrap_reproduction(exec_ctx)
    assert outcome.status == "OUTPUT_PRODUCED", outcome.error_message
    assert outcome.output is not None
    assert outcome.output.get("reproduced") is not True, outcome.output
    await db_session.refresh(defect)
    assert defect.status == "NOT_REPRODUCIBLE"
