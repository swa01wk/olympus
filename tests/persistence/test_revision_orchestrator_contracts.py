"""RL2.2 — revision context on orchestrator contracts without changing default hashes."""

from __future__ import annotations

import uuid

import pytest
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import DeliveryCycleType
from core.domain.task_contracts.models import TaskContract
from core.planning.orchestrator import PlanningOrchestrator
from core.review.context import RevisionContext

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_architecture_proposal_without_revision_unchanged(
    db_session, sample_project, operator_ctx
) -> None:
    cycle = DeliveryCycle(
        project_id=sample_project.id,
        key="RL22",
        type=DeliveryCycleType.GREENFIELD_BUILD,
        objective="revision contract test",
        state="ARCHITECTURE",
        state_version=0,
        opened_by_actor_id=operator_ctx.actor.id,
    )
    db_session.add(cycle)
    await db_session.flush()

    started = await PlanningOrchestrator().start_architecture_proposal(
        db_session, cycle.id, operator_ctx
    )
    contract = await db_session.get(TaskContract, uuid.UUID(started["contract_id"]))
    assert contract is not None
    assert contract.content_hash == f"atlas-{cycle.id}"
    assert "_snapshot" not in contract.body


@pytest.mark.asyncio
async def test_architecture_proposal_with_revision_merges_snapshot(
    db_session, sample_project, operator_ctx
) -> None:
    cycle = DeliveryCycle(
        project_id=sample_project.id,
        key="RL22R",
        type=DeliveryCycleType.GREENFIELD_BUILD,
        objective="revision contract test",
        state="ARCHITECTURE",
        state_version=0,
        opened_by_actor_id=operator_ctx.actor.id,
    )
    db_session.add(cycle)
    await db_session.flush()

    approval_id = uuid.uuid4()
    revision = RevisionContext(
        approval_id=approval_id,
        feedback="Use one guard.",
        previous_output_json='{"decisions": []}',
        subject_type="architecture",
        subject_id=uuid.uuid4(),
    )
    started = await PlanningOrchestrator().start_architecture_proposal(
        db_session, cycle.id, operator_ctx, revision=revision
    )
    contract = await db_session.get(TaskContract, uuid.UUID(started["contract_id"]))
    assert contract is not None
    assert contract.content_hash == f"atlas-{cycle.id}"
    snap = contract.body.get("_snapshot") or {}
    assert snap["revision_feedback"] == "Use one guard."
    assert snap["previous_output_json"] == '{"decisions": []}'
    assert snap["revision_of_approval_id"] == str(approval_id)
