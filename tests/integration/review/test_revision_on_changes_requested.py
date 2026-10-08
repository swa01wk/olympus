"""RL2.3 — CHANGES_REQUESTED schedules a revision run and completes with supersession."""

from __future__ import annotations

import pytest
from core.commands.handlers import handle_approval_decide
from core.domain.approvals.models import Approval
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ApprovalStatus, DeliveryCycleType, ExecutionStatus, SpecStatus
from core.domain.executions.models import Execution
from core.domain.task_contracts.models import TaskContract
from core.domain.tasks.models import Task
from core.planning.architecture.service import ArchitectureService
from core.planning.completion import PlanningCompletionService
from core.planning.models import Architecture
from core.review.service import RevisionService
from sqlalchemy import select
from tests.fixtures.planning_harness import supportdesk_architecture_proposal
from tests.fixtures.planning_workflow_harness import seed_supportdesk_product_and_approved_scope

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_architecture_changes_requested_schedules_revision_task(
    db_session, sample_project, operator_ctx
) -> None:
    cycle = DeliveryCycle(
        project_id=sample_project.id,
        key="REV",
        type=DeliveryCycleType.GREENFIELD_BUILD,
        objective="revision test",
        state="ARCHITECTURE",
        state_version=0,
        opened_by_actor_id=operator_ctx.actor.id,
    )
    db_session.add(cycle)
    await db_session.flush()

    await seed_supportdesk_product_and_approved_scope(
        db_session, sample_project.id, cycle.id, operator_ctx
    )

    arch_v1 = await ArchitectureService().persist_proposal(
        db_session,
        project_id=sample_project.id,
        proposal=supportdesk_architecture_proposal(),
        execution_id=None,
        ctx=operator_ctx,
    )
    approval_id = await ArchitectureService().request_approval(
        db_session, arch_v1.id, cycle.id, operator_ctx
    )

    await handle_approval_decide(
        db_session,
        operator_ctx,
        {
            "approval_id": str(approval_id),
            "decision": ApprovalStatus.CHANGES_REQUESTED.value,
            "note": "Use one ProjectGuard.",
        },
    )

    approval = await db_session.get(Approval, approval_id)
    assert approval is not None
    svc = RevisionService()
    task_id = await svc.find_revision_task_id(db_session, approval_id, cycle.id)
    assert task_id is not None
    same = await svc.request_revision(db_session, approval, operator_ctx)
    assert same == task_id

    contract = (
        await db_session.execute(
            select(TaskContract)
            .join(Task, TaskContract.task_id == Task.id)
            .where(Task.id == task_id)
        )
    ).scalar_one()
    assert contract.body.get("agent_profile") == "atlas.propose_architecture"
    snap = contract.body.get("_snapshot") or {}
    assert snap.get("revision_feedback") == "Use one ProjectGuard."
    assert snap.get("revision_of_approval_id") == str(approval_id)
    assert "decisions" in (snap.get("previous_output_json") or "")

    execution = Execution(
        key="rev-ex",
        task_id=task_id,
        delivery_cycle_id=cycle.id,
        task_contract_id=contract.id,
        attempt_number=1,
        status=ExecutionStatus.COMPLETED,
        executor_kind="AGENT_RUNTIME",
        agent_profile="atlas.propose_architecture",
    )
    db_session.add(execution)
    await db_session.flush()

    proposal_v2 = supportdesk_architecture_proposal()
    proposal_v2.body.summary = "Revised with one guard"
    await PlanningCompletionService().persist_from_execution(
        db_session,
        execution,
        "atlas.propose_architecture",
        proposal_v2.model_dump(mode="json"),
        operator_ctx,
    )

    arch_v1_row = await db_session.get(Architecture, arch_v1.id)
    assert arch_v1_row is not None
    assert arch_v1_row.status == SpecStatus.SUPERSEDED

    arch_rows = (
        await db_session.execute(
            select(Architecture)
            .where(Architecture.project_id == sample_project.id)
            .order_by(Architecture.version.desc())
        )
    ).scalars()
    versions = list(arch_rows)
    assert len(versions) >= 2
    assert versions[0].status == SpecStatus.PROPOSED
    assert versions[0].version == arch_v1.version + 1
