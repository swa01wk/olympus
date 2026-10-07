from __future__ import annotations

import pytest
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import DeliveryCycleType, KnowledgeClass, TaskOrigin, WorkType
from core.domain.tasks.service import TaskService
from core.execution.snapshots.product_context import product_context_for_task
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
