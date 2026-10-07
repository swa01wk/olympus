from __future__ import annotations

import uuid

from core.commands.context import CommandContext
from core.intelligence.baselines.service import BaselineService
from core.intelligence.recovered_specs.promotion import PromotionService
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import command_context, get_db

router = APIRouter(tags=["promotion"])


class PromotionDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_type: str
    subject_id: uuid.UUID
    decision: str
    note: str | None = None


class PromotionDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject_type: str
    subject_id: uuid.UUID
    decision: str
    note: str | None


class ReviewQueueItem(BaseModel):
    subject_type: str
    subject_id: str
    detail: dict[str, object]
    decided: bool
    decision: str | None


@router.get(
    "/delivery-cycles/{cycle_id}/review-queue",
    response_model=list[ReviewQueueItem],
)
async def review_queue(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[ReviewQueueItem]:
    items = await BaselineService().review_queue(session, cycle_id)
    return [ReviewQueueItem.model_validate(item) for item in items]


@router.post(
    "/delivery-cycles/{cycle_id}/promotion-decisions",
    response_model=PromotionDecisionResponse,
    status_code=201,
)
async def create_promotion_decision(
    cycle_id: uuid.UUID,
    body: PromotionDecisionRequest,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> PromotionDecisionResponse:
    row = await PromotionService().decide(
        session,
        cycle_id,
        body.subject_type,
        body.subject_id,
        body.decision,
        body.note,
        ctx,
    )
    return PromotionDecisionResponse(
        id=row.id,
        subject_type=row.subject_type,
        subject_id=row.subject_id,
        decision=row.decision,
        note=row.note,
    )
