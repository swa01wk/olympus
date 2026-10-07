"""DB integration: reproduction.run PRE_REPAIR on defect fixture worktree."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from core.assurance.enums import EvidenceResult, EvidenceType
from core.assurance.models import Evidence
from core.assurance.reproduction.register import _wrap_reproduction
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import TaskStatus
from core.domain.exceptions import DomainError
from core.domain.executions.models import Execution
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import parse_task_contract_body
from core.domain.tasks.models import Task
from core.execution.executors.base import ExecutionContext
from core.execution.snapshots.builder import SnapshotBuilder
from core.product_model.defects.models import Reproduction
from core.product_model.defects.service import DefectService
from core.scheduler.admission import AdmissionService
from sqlalchemy import select
from tests.journey.bug_fix_helpers import (
    _ensure_reproduction_run_ready,
    maybe_apply_reproduce_fallback,
    maybe_apply_triage_fallback,
)
from tests.journey.seed import seed_trusted_project

DEFECT_REPO = (
    Path(__file__).resolve().parents[2] / "fixtures" / "repos" / "supportdesk_defect_closed_update"
)
TRUSTED_SEED_DEFECT = (
    Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "trusted_seed_defect.yaml"
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reproduction_run_pre_repair_reproduced(
    db_session, system_ctx: CommandContext
) -> None:
    trusted = await seed_trusted_project(db_session, DEFECT_REPO, TRUSTED_SEED_DEFECT, system_ctx)
    defect = await DefectService().intake(
        db_session,
        project_id=trusted.project_id,
        title="CLOSED ticket 500",
        description="PATCH on CLOSED ticket returns 500 not 409",
        source_type="test",
        external_ref="repro-db-1",
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
    await maybe_apply_reproduce_fallback(db_session, cycle_id, system_ctx)
    await _ensure_reproduction_run_ready(db_session, cycle_id, system_ctx)
    await db_session.flush()

    task = (
        await db_session.execute(
            select(Task).where(
                Task.delivery_cycle_id == cycle_id,
                Task.title == "Run reproduction test",
            )
        )
    ).scalar_one()
    assert task.status == TaskStatus.READY, task.status
    try:
        execution = await AdmissionService().admit_task(db_session, task.id, system_ctx)
    except DomainError as exc:
        raise AssertionError(f"admission failed: {exc.details or exc.message}") from exc
    exec_id = execution.id
    assert exec_id is not None
    execution = await db_session.get(Execution, exec_id)
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
        worker_id="repro-int-test",
        contract_payload=contract_row.body if isinstance(contract_row.body, dict) else {},
        session=db_session,
    )
    outcome = await _wrap_reproduction(exec_ctx)
    assert outcome.status == "OUTPUT_PRODUCED", outcome.error_message
    assert outcome.output is not None
    assert outcome.output.get("reproduced") is True, outcome.output

    ev = (
        await db_session.execute(
            select(Evidence).where(
                Evidence.delivery_cycle_id == cycle_id,
                Evidence.evidence_type == EvidenceType.REPRODUCTION,
                Evidence.result == EvidenceResult.FAIL,
            )
        )
    ).scalar_one()
    assert ev.details.get("reproduced") is True
    assert ev.details.get("phase") == "PRE_REPAIR"
    repro = (
        await db_session.execute(
            select(Reproduction).where(
                Reproduction.defect_id == defect.id, Reproduction.phase == "PRE_REPAIR"
            )
        )
    ).scalar_one()
    assert repro.outcome == "REPRODUCED"
