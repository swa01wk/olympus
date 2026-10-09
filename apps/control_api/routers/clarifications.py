from __future__ import annotations

import uuid
from datetime import UTC, datetime

from core.commands.context import CommandContext
from core.domain.enums import ClarificationStatus
from core.domain.executions.models import Clarification
from core.execution.resume import ResumeService
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import command_context, get_db

router = APIRouter(tags=["clarifications"])


class ClarificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    key: str
    question: str
    status: str
    answer: str | None


class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str


@router.get("/clarifications", response_model=list[ClarificationResponse])
async def list_clarifications(
    status: str | None = None,
    project_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[ClarificationResponse]:
    stmt = select(Clarification)
    if project_id is not None:
        stmt = stmt.where(Clarification.project_id == project_id)
    if status:
        stmt = stmt.where(Clarification.status == ClarificationStatus(status))
    result = await session.execute(stmt)
    return [
        ClarificationResponse(
            id=c.id,
            key=c.key,
            question=c.question,
            status=c.status.value,
            answer=c.answer,
        )
        for c in result.scalars()
    ]


@router.get("/clarifications/{clarification_id}", response_model=ClarificationResponse)
async def get_clarification(
    clarification_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ClarificationResponse:
    row = await session.get(Clarification, clarification_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Clarification not found")
    return ClarificationResponse(
        id=row.id,
        key=row.key,
        question=row.question,
        status=row.status.value,
        answer=row.answer,
    )


@router.post("/clarifications/{clarification_id}/answer")
async def answer_clarification(
    clarification_id: uuid.UUID,
    body: AnswerRequest,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, object]:
    row = await session.get(Clarification, clarification_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Clarification not found")
    row.answer = body.answer
    row.status = ClarificationStatus.ANSWERED
    row.answered_by_actor_id = ctx.actor.id
    row.answered_at = datetime.now(UTC)
    from core.product_model.knowledge import KnowledgeService

    await KnowledgeService().create_decision_from_clarification(
        session,
        project_id=row.project_id,
        delivery_cycle_id=row.delivery_cycle_id,
        clarification_id=row.id,
        statement=body.answer,
        ctx=ctx,
    )
    payload: dict[str, object] = {"status": "ANSWERED"}
    if row.execution_id is not None:
        try:
            decision = await ResumeService().on_clarification_answered(
                session, clarification_id, ctx
            )
            payload["resume"] = decision.action
            payload["execution_id"] = str(decision.execution_id)
        except ValueError:
            payload["resume"] = "SKIPPED"
    else:
        payload["resume"] = "PRODUCT_REDECOMPOSE"

    redecompose: dict[str, str] | None = None
    if row.delivery_cycle_id is not None:
        from core.product_model.decomposition import DecompositionOrchestrator

        redecompose = await DecompositionOrchestrator().redecompose_after_clarification(
            session,
            delivery_cycle_id=row.delivery_cycle_id,
            ctx=ctx,
        )
    if redecompose is not None:
        payload["redecompose_task_id"] = redecompose["task_id"]
    return payload
