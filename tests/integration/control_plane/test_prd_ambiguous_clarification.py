from __future__ import annotations

import uuid
from pathlib import Path
from uuid import uuid4

import pytest
from core.domain.enums import KnowledgeClass
from core.product_model.models import KnowledgeItem
from core.product_model.schemas import ClarificationDraft
from sqlalchemy import select


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ambiguous_prd_decompose_persists_open_question_and_decision_on_answer(
    api_client, async_engine
) -> None:
    """Deterministic stand-in for live PRD_ambiguous clarification round (§12)."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from tests.fixtures.product_model_harness import supportdesk_decomposition

    proposal = supportdesk_decomposition()
    proposal = proposal.model_copy(
        update={
            "open_questions": [
                ClarificationDraft(
                    question="How should closed tickets behave on update?",
                    context="PRD ambiguous on closed ticket edits",
                    blocking=True,
                )
            ]
        }
    )

    key = f"amb-{uuid4().hex[:6]}"
    project = await api_client.post("/projects", json={"key": key, "name": "Amb"})
    project_id = project.json()["id"]
    cycle = await api_client.post(
        f"/projects/{project_id}/delivery-cycles",
        json={"type": "GREENFIELD_BUILD", "objective": "amb"},
    )
    cycle_id = cycle.json()["id"]
    prd = Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "PRD_ambiguous.md"
    await api_client.post(
        f"/projects/{project_id}/sources",
        params={"delivery_cycle_id": cycle_id},
        files={"file": ("PRD_ambiguous.md", prd.read_bytes(), "text/markdown")},
        headers={"Idempotency-Key": f"amb-{uuid4().hex[:8]}"},
    )

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        from core.commands.context import CommandContext
        from core.domain.actors.models import Actor
        from core.domain.enums import ActorKind, ClarificationStatus
        from core.domain.executions.models import Clarification
        from core.domain.sequences import next_project_key
        from core.product_model.models import ProductSource
        from core.product_model.service import ProductModelService

        actor = (
            await session.execute(select(Actor).where(Actor.kind == ActorKind.HUMAN).limit(1))
        ).scalar_one()
        ctx = CommandContext(actor=actor, correlation_id="amb")
        source = (
            await session.execute(
                select(ProductSource).where(ProductSource.project_id == uuid.UUID(project_id))
            )
        ).scalar_one()
        await ProductModelService().persist_proposal(
            session,
            project_id=uuid.UUID(project_id),
            delivery_cycle_id=uuid.UUID(cycle_id),
            product_source_version_id=source.id,
            execution_id=None,
            proposal=proposal,
            ctx=ctx,
        )
        cl_key = await next_project_key(
            session, uuid.UUID(project_id), "clarification", prefix="CL"
        )
        cl = Clarification(
            key=cl_key,
            project_id=uuid.UUID(project_id),
            delivery_cycle_id=uuid.UUID(cycle_id),
            question=proposal.open_questions[0].question,
            context={"text": proposal.open_questions[0].context},
            options=[],
            blocking=True,
            status=ClarificationStatus.OPEN,
        )
        session.add(cl)
        await session.flush()
        clarification_id = str(cl.id)

    answer = await api_client.post(
        f"/clarifications/{clarification_id}/answer",
        json={"answer": "Return HTTP 409 when updating a closed ticket"},
    )
    assert answer.status_code == 200, answer.text
    assert answer.json().get("redecompose_task_id")

    async with factory() as session:
        decisions = await session.execute(
            select(KnowledgeItem).where(
                KnowledgeItem.delivery_cycle_id == uuid.UUID(cycle_id),
                KnowledgeItem.knowledge_class == KnowledgeClass.DECISION,
            )
        )
        assert decisions.scalars().first() is not None
