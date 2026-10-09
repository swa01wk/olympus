"""kira.expected_behavior sees approved ACs as SPEC/AC citations; citations resolve per project."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from core.commands.context import CommandContext
from core.domain.exceptions import DomainError
from core.domain.task_contracts.models import TaskContract
from core.domain.tasks.models import Task
from core.product_model.defects.orchestrator import BugFixOrchestrator
from core.product_model.defects.schemas import ExpectedBehaviorProposal
from core.product_model.defects.service import DefectService
from core.product_model.models import AcceptanceCriterion
from core.scheduler.admission import AdmissionService
from sqlalchemy import select
from tests.journey.bug_fix_helpers import maybe_apply_triage_fallback
from tests.journey.seed import seed_trusted_project

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
DEFECT_REPO = FIXTURES / "repos" / "supportdesk_defect_closed_update"
TRUSTED_SEED_DEFECT = FIXTURES / "supportdesk" / "trusted_seed_defect.yaml"
CLOSED_AC = "SPEC-FEAT-TICKETS/AC-TICKET-CLOSED-UPDATE-409"


def _proposal(*citations: str) -> ExpectedBehaviorProposal:
    return ExpectedBehaviorProposal(
        classification="SPECIFIED",
        cited_ac_lineage_keys=list(citations),
        expected_behavior_statement="PATCH on a CLOSED ticket returns 409",
    )


async def test_expected_behavior_citations(db_session, system_ctx: CommandContext) -> None:
    trusted = await seed_trusted_project(db_session, DEFECT_REPO, TRUSTED_SEED_DEFECT, system_ctx)
    svc = DefectService()
    defect = await svc.intake(
        db_session,
        project_id=trusted.project_id,
        title="CLOSED ticket 500",
        description="PATCH on CLOSED ticket returns 500 not 409",
        source_type="test",
        external_ref="eb-citations-1",
        inbound_event_id=None,
        ctx=system_ctx,
    )
    cycle_id = defect.delivery_cycle_id
    assert cycle_id is not None
    assert await maybe_apply_triage_fallback(db_session, cycle_id, system_ctx)
    await db_session.refresh(defect)

    citations = await svc.approved_ac_citations(db_session, defect)
    assert CLOSED_AC in [c["citation"] for c in citations]
    task = (
        await db_session.execute(
            select(Task).where(
                Task.delivery_cycle_id == cycle_id, Task.title == "Author reproduction test"
            )
        )
    ).scalar_one()
    execution = await AdmissionService().admit_task(db_session, task.id, system_ctx)

    with pytest.raises(DomainError, match="AC not approved: SPEC-FEAT-TICKETS"):
        await svc.persist_expected_behavior(
            db_session, cycle_id, _proposal("SPEC-FEAT-TICKETS"), execution.id, system_ctx
        )

    await svc.persist_expected_behavior(
        db_session, cycle_id, _proposal(CLOSED_AC), execution.id, system_ctx
    )
    await db_session.refresh(defect)
    ac = await db_session.get(AcceptanceCriterion, uuid.UUID(defect.expected_ac_ids[0]))
    assert ac is not None and ac.lineage_key == "AC-TICKET-CLOSED-UPDATE-409"

    await BugFixOrchestrator().schedule_repair_implementation_spec(db_session, cycle_id, system_ctx)
    repair = (
        await db_session.execute(
            select(Task).where(
                Task.delivery_cycle_id == cycle_id, Task.title == "Draft REPAIR implementation spec"
            )
        )
    ).scalar_one()
    contract = await db_session.get(TaskContract, repair.current_contract_id)
    assert contract is not None
    snap = contract.body["_snapshot"]
    assert snap["expected_behavior"] == "PATCH on a CLOSED ticket returns 409"
    assert json.loads(snap["root_cause_json"]) == {}, "no root cause recorded yet"


async def test_expected_behavior_contract_lists_citations(
    db_session, system_ctx: CommandContext
) -> None:
    trusted = await seed_trusted_project(db_session, DEFECT_REPO, TRUSTED_SEED_DEFECT, system_ctx)
    defect = await DefectService().intake(
        db_session,
        project_id=trusted.project_id,
        title="CLOSED ticket 500",
        description="PATCH on CLOSED ticket returns 500 not 409",
        source_type="test",
        external_ref="eb-citations-2",
        inbound_event_id=None,
        ctx=system_ctx,
    )
    cycle_id = defect.delivery_cycle_id
    assert cycle_id is not None
    assert await maybe_apply_triage_fallback(db_session, cycle_id, system_ctx)
    await BugFixOrchestrator().schedule_expected_behavior(db_session, cycle_id, system_ctx)

    task = (
        await db_session.execute(
            select(Task).where(
                Task.delivery_cycle_id == cycle_id, Task.title == "Resolve expected behavior"
            )
        )
    ).scalar_one()
    contract = await db_session.get(TaskContract, task.current_contract_id)
    assert contract is not None
    listed = json.loads(contract.body["_snapshot"]["approved_acs_json"])
    assert listed[0]["feature_key"] == "FEAT-TICKETS", "triaged feature first"
    assert CLOSED_AC in [c["citation"] for c in listed]
