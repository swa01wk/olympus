from __future__ import annotations

import uuid

from core.commands.context import CommandContext
from core.intelligence.baselines.readiness import ReadinessService
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import command_context, get_db

router = APIRouter(tags=["readiness"])


class ReadinessAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    delivery_cycle_id: uuid.UUID
    commit_sha: str
    metrics: list[dict[str, object]]
    result: str
    remediable: bool
    reasons: list[str]


@router.get(
    "/delivery-cycles/{cycle_id}/readiness",
    response_model=ReadinessAssessmentResponse | None,
)
async def get_readiness(
    cycle_id: uuid.UUID,
    recompute: bool = Query(default=False),
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> ReadinessAssessmentResponse | None:
    row = await ReadinessService().assess(session, cycle_id, ctx, recompute=recompute)
    return ReadinessAssessmentResponse(
        id=row.id,
        delivery_cycle_id=row.delivery_cycle_id,
        commit_sha=row.commit_sha,
        metrics=row.metrics,
        result=row.result.value,
        remediable=row.remediable,
        reasons=list(row.reasons or []),
    )
