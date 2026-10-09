from __future__ import annotations

import pytest
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import DeliveryCycleType, KnowledgeClass, TaskOrigin, WorkType
from core.domain.tasks.service import TaskService
from core.execution.snapshots.product_context import product_context_for_task, protected_test_refs
from core.intelligence.baselines.enums import (
    BaselineActivation,
    BaselineCheckKind,
    BaselineSource,
    BaselineStatus,
)
from core.intelligence.baselines.models import BehavioralBaseline
from core.product_model.models import KnowledgeItem


@pytest.mark.persistence
@pytest.mark.asyncio
async def test_snapshot_product_context_includes_decisions(
    db_session, sample_project, operator_ctx
) -> None:
    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "ctx",
        operator_ctx,
    )
    task = await TaskService().create_task(
        db_session,
        cycle.id,
        "analyze",
        WorkType.ANALYSIS,
        TaskOrigin.CONTROL_PLANE,
        operator_ctx,
    )
    db_session.add(
        KnowledgeItem(
            project_id=sample_project.id,
            delivery_cycle_id=cycle.id,
            knowledge_class=KnowledgeClass.DECISION,
            statement="Closed tickets return 409",
            subject_refs=[],
            provenance={},
            blocking=False,
        )
    )
    await db_session.flush()
    ctx = await product_context_for_task(db_session, task)
    assert ctx["project_name"] == sample_project.name
    assert "409" in ctx["decision_items"][0]


@pytest.mark.persistence
@pytest.mark.asyncio
async def test_protected_test_refs_are_active_baseline_check_refs(
    db_session, sample_project, operator_ctx
) -> None:
    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "ctx-bl",
        operator_ctx,
    )
    task = await TaskService().create_task(
        db_session,
        cycle.id,
        "implement",
        WorkType.CODE_CHANGE,
        TaskOrigin.IMPLEMENTATION_PLAN,
        operator_ctx,
    )
    db_session.add(
        BehavioralBaseline(
            project_id=sample_project.id,
            lineage_key="BL-TICKET-CREATE",
            version=1,
            status=BaselineStatus.ACTIVE,
            source=BaselineSource.BROWNFIELD_EXISTING_TEST,
            given="a caller creates a ticket",
            when="POST /tickets",
            then="HTTP 201",
            check_kind=BaselineCheckKind.EXISTING_TEST,
            check_ref="tests/test_tickets_api.py::test_create_ticket",
            observed_behavior_ids=[],
            exercised_stable_keys=[],
            established_sha="abc",
            activation=BaselineActivation.HUMAN,
        )
    )
    db_session.add(
        BehavioralBaseline(
            project_id=sample_project.id,
            lineage_key="BL-TICKET-DEFAULT-OPEN",
            version=1,
            status=BaselineStatus.SUPERSEDED,
            source=BaselineSource.BROWNFIELD_EXISTING_TEST,
            given="a caller creates a ticket",
            when="POST /tickets",
            then="status OPEN",
            check_kind=BaselineCheckKind.EXISTING_TEST,
            check_ref="tests/test_ticket_service.py::test_create_defaults_open",
            observed_behavior_ids=[],
            exercised_stable_keys=[],
            established_sha="abc",
            activation=BaselineActivation.HUMAN,
        )
    )
    await db_session.flush()
    assert await protected_test_refs(db_session, task) == [
        "tests/test_tickets_api.py::test_create_ticket"
    ]
