from __future__ import annotations

import uuid

import pytest
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import ClarificationStatus, DeliveryCycleType, TaskStatus
from core.domain.executions.models import Clarification, Execution
from core.domain.sequences import next_project_key
from core.domain.tasks.models import Task
from core.execution.snapshots.product_context import product_context_for_task
from core.product_model.decomposition import DecompositionOrchestrator
from core.product_model.knowledge import KnowledgeService
from core.product_model.models import ProductSource
from core.product_model.schemas import ClarificationDraft
from core.product_model.service import ProductModelService
from core.product_model.sources.service import ProductSourceService
from sqlalchemy import select
from tests.fixtures.product_model_harness import supportdesk_decomposition

pytestmark = pytest.mark.persistence


async def _cycle_with_source(db_session, sample_project, operator_ctx, label: str):
    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        label,
        operator_ctx,
    )
    ingest = await ProductSourceService().ingest(
        db_session,
        project_id=sample_project.id,
        lineage_key=f"{label}-src",
        source_type="PRD",
        title="PRD.md",
        mime_type="text/markdown",
        content_hash=f"{label}-{uuid.uuid4().hex}",
        raw_storage_ref=f"inbound/sha256/x/{label}",
        text="# SupportDesk",
        ctx=operator_ctx,
        delivery_cycle_id=cycle.id,
    )
    source = await db_session.get(ProductSource, ingest["product_source_id"])
    assert source is not None
    return cycle, source


async def _queue_execution(db_session, task: Task, key: str) -> Execution:
    assert task.current_contract_id is not None
    task.status = TaskStatus.QUEUED
    execution = Execution(
        key=key,
        task_id=task.id,
        delivery_cycle_id=task.delivery_cycle_id,
        task_contract_id=task.current_contract_id,
        attempt_number=1,
        status="QUEUED",
        executor_kind="AGENT_RUNTIME",
    )
    db_session.add(execution)
    await db_session.flush()
    return execution


async def _decompose_task_count(db_session, cycle_id: uuid.UUID) -> int:
    rows = await db_session.execute(select(Task.id).where(Task.delivery_cycle_id == cycle_id))
    return len(rows.all())


@pytest.mark.asyncio
async def test_redecompose_reuses_task_until_its_execution_is_leased(
    db_session, sample_project, operator_ctx
) -> None:
    cycle, _ = await _cycle_with_source(db_session, sample_project, operator_ctx, "rd-reuse")
    orchestrator = DecompositionOrchestrator()

    first = await orchestrator.redecompose_after_clarification(
        db_session, delivery_cycle_id=cycle.id, ctx=operator_ctx
    )
    assert first is not None
    again_ready = await orchestrator.redecompose_after_clarification(
        db_session, delivery_cycle_id=cycle.id, ctx=operator_ctx
    )
    assert again_ready is not None and again_ready["task_id"] == first["task_id"]

    task = await db_session.get(Task, uuid.UUID(first["task_id"]))
    assert task is not None
    execution = await _queue_execution(db_session, task, "E-RD-1")
    again_queued = await orchestrator.redecompose_after_clarification(
        db_session, delivery_cycle_id=cycle.id, ctx=operator_ctx
    )
    assert again_queued is not None and again_queued["task_id"] == first["task_id"]
    assert await _decompose_task_count(db_session, cycle.id) == 1

    execution.status = "LEASED"
    await db_session.flush()
    after_lease = await orchestrator.redecompose_after_clarification(
        db_session, delivery_cycle_id=cycle.id, ctx=operator_ctx
    )
    assert after_lease is not None and after_lease["task_id"] != first["task_id"]
    assert await _decompose_task_count(db_session, cycle.id) == 2


@pytest.mark.asyncio
async def test_new_decomposition_cancels_open_questions_from_superseded_one(
    db_session, sample_project, operator_ctx
) -> None:
    cycle, source = await _cycle_with_source(db_session, sample_project, operator_ctx, "rd-cancel")
    orchestrator = DecompositionOrchestrator()
    service = ProductModelService()

    async def decompose_with_questions(key: str, questions: list[str]) -> Execution:
        started = await orchestrator.start_decomposition(
            db_session, source=source, delivery_cycle_id=cycle.id, ctx=operator_ctx
        )
        task = await db_session.get(Task, uuid.UUID(started["task_id"]))
        assert task is not None
        execution = await _queue_execution(db_session, task, key)
        proposal = supportdesk_decomposition().model_copy(
            update={
                "open_questions": [
                    ClarificationDraft(question=q, context="ctx", blocking=True) for q in questions
                ]
            }
        )
        await service.persist_proposal(
            db_session,
            project_id=sample_project.id,
            delivery_cycle_id=cycle.id,
            product_source_version_id=source.id,
            execution_id=execution.id,
            proposal=proposal,
            ctx=operator_ctx,
        )
        return execution

    first = await decompose_with_questions("E-RD-A", ["Q-answered", "Q-stale"])
    answered = (
        await db_session.execute(
            select(Clarification).where(
                Clarification.execution_id == first.id, Clarification.question == "Q-answered"
            )
        )
    ).scalar_one()
    answered.status = ClarificationStatus.ANSWERED
    answered.answer = "yes"
    await db_session.flush()

    await decompose_with_questions("E-RD-B", ["Q-new"])

    rows = (
        await db_session.execute(
            select(Clarification.question, Clarification.status).where(
                Clarification.delivery_cycle_id == cycle.id
            )
        )
    ).all()
    status_by_question = {q: s for q, s in rows}
    assert status_by_question == {
        "Q-answered": ClarificationStatus.ANSWERED,
        "Q-stale": ClarificationStatus.CANCELLED,
        "Q-new": ClarificationStatus.OPEN,
    }


@pytest.mark.asyncio
async def test_decision_items_pair_answer_with_its_question(
    db_session, sample_project, operator_ctx
) -> None:
    cycle, _ = await _cycle_with_source(db_session, sample_project, operator_ctx, "rd-qa")
    cl = Clarification(
        key=await next_project_key(db_session, sample_project.id, "clarification", prefix="CL"),
        project_id=sample_project.id,
        delivery_cycle_id=cycle.id,
        question="What does Get Ticket return for an unknown id?",
        context={},
        options=[],
        blocking=True,
        status=ClarificationStatus.ANSWERED,
        answer="HTTP 404",
    )
    db_session.add(cl)
    await db_session.flush()
    await KnowledgeService().create_decision_from_clarification(
        db_session,
        project_id=sample_project.id,
        delivery_cycle_id=cycle.id,
        clarification_id=cl.id,
        statement="HTTP 404",
        ctx=operator_ctx,
    )
    started = await DecompositionOrchestrator().redecompose_after_clarification(
        db_session, delivery_cycle_id=cycle.id, ctx=operator_ctx
    )
    assert started is not None
    task = await db_session.get(Task, uuid.UUID(started["task_id"]))
    assert task is not None

    ctx = await product_context_for_task(db_session, task)

    assert ctx["decision_items"] == [
        "Q: What does Get Ticket return for an unknown id?\n  A: HTTP 404"
    ]
