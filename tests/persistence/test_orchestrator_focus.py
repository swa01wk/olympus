"""RL2.6 — orchestrator focus loaders and snapshot overview."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from agents.orchestrator.schemas import OrchestratorTurn, RevisionNoteDraft
from core.domain.approvals.models import Approval
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ApprovalStatus, ApprovalType, DeliveryCycleType, SpecStatus
from core.orchestrator.focus import load_focus
from core.orchestrator.models import OrchestratorSession
from core.orchestrator.service import OrchestratorService
from core.planning.architecture.service import ArchitectureService
from tests.fixtures.planning_harness import supportdesk_architecture_proposal
from tests.fixtures.planning_workflow_harness import seed_supportdesk_product_and_approved_scope

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_build_snapshot_uses_cycle_overview_when_both_ids(
    db_session, sample_project, operator_ctx
) -> None:
    cycle = DeliveryCycle(
        project_id=sample_project.id,
        key="ORCH",
        type=DeliveryCycleType.GREENFIELD_BUILD,
        objective="orch snapshot",
        state="ARCHITECTURE",
        state_version=0,
        opened_by_actor_id=operator_ctx.actor.id,
    )
    db_session.add(cycle)
    await db_session.flush()

    orch = OrchestratorSession(
        actor_id=operator_ctx.actor.id,
        project_id=sample_project.id,
        delivery_cycle_id=cycle.id,
        turns=[],
        expires_at=(datetime.now(UTC) + timedelta(hours=1)).replace(tzinfo=None),
    )
    db_session.add(orch)
    await db_session.flush()

    snap = await OrchestratorService().build_snapshot(db_session, orch, operator_ctx)
    assert snap["cycle_overview"] is not None
    assert snap["cycle_overview"]["delivery_cycle_id"] == str(cycle.id)
    assert snap["project_overview"] is not None
    assert snap["overview"]["delivery_cycle_id"] == str(cycle.id)


@pytest.mark.asyncio
async def test_architecture_focus_loader(db_session, sample_project, operator_ctx) -> None:
    cycle = DeliveryCycle(
        project_id=sample_project.id,
        key="FOC",
        type=DeliveryCycleType.GREENFIELD_BUILD,
        objective="focus",
        state="ARCHITECTURE",
        state_version=0,
        opened_by_actor_id=operator_ctx.actor.id,
    )
    db_session.add(cycle)
    await db_session.flush()
    await seed_supportdesk_product_and_approved_scope(
        db_session, sample_project.id, cycle.id, operator_ctx
    )
    arch = await ArchitectureService().persist_proposal(
        db_session,
        project_id=sample_project.id,
        proposal=supportdesk_architecture_proposal(),
        execution_id=None,
        ctx=operator_ctx,
    )
    focus = await load_focus(db_session, "architecture", arch.id)
    assert focus is not None
    assert focus["type"] == "architecture"
    assert focus["key"] == "ARCH"
    assert focus["status"] == SpecStatus.PROPOSED.value
    assert focus["body"]


@pytest.mark.asyncio
async def test_complete_turn_persists_revision_and_navigate(
    db_session, sample_project, operator_ctx
) -> None:
    cycle = DeliveryCycle(
        project_id=sample_project.id,
        key="TURN",
        type=DeliveryCycleType.GREENFIELD_BUILD,
        objective="turn",
        state="ARCHITECTURE",
        state_version=0,
        opened_by_actor_id=operator_ctx.actor.id,
    )
    db_session.add(cycle)
    await db_session.flush()

    approval = Approval(
        key="APR-FOC",
        project_id=sample_project.id,
        delivery_cycle_id=cycle.id,
        approval_type=ApprovalType.ARCHITECTURE,
        subject_type="architecture",
        subject_id=uuid.uuid4(),
        subject_version=1,
        subject_hash="hash",
        status=ApprovalStatus.PENDING,
        requested_by_actor_id=operator_ctx.actor.id,
    )
    db_session.add(approval)
    await db_session.flush()

    orch = OrchestratorSession(
        actor_id=operator_ctx.actor.id,
        project_id=sample_project.id,
        delivery_cycle_id=cycle.id,
        turns=[{"role": "user", "text": "change the guard"}],
        expires_at=(datetime.now(UTC) + timedelta(hours=1)).replace(tzinfo=None),
    )
    db_session.add(orch)
    await db_session.flush()

    turn = OrchestratorTurn(
        intent="REVISION_NOTE_DRAFT",
        message="Use one guard.",
        refs=["ARCH"],
        revision_note_draft=RevisionNoteDraft(
            approval_id=str(approval.id),
            note="Use one ProjectGuard.",
        ),
        navigate_to="ARCHITECTURE",
    )
    await OrchestratorService().complete_turn(
        db_session,
        orch,
        execution_id=uuid.uuid4(),
        turn=turn,
        ctx=operator_ctx,
    )
    assistant = [t for t in orch.turns if t.get("role") == "assistant"][-1]
    assert assistant["revision_note_draft"]["note"] == "Use one ProjectGuard."
    assert assistant["navigate_to"] == "ARCHITECTURE"
    assert assistant["refs"] == ["ARCH"]
