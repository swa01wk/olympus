from __future__ import annotations

import uuid

from core.commands.context import CommandContext
from core.product_model.specifications.delta import SpecDeltaService
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import command_context, get_db

router = APIRouter(tags=["spec-deltas"])


class ComputeSpecDeltaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_spec_id: uuid.UUID | None = None
    to_spec_id: uuid.UUID
    delivery_cycle_id: uuid.UUID


@router.post("/features/{feature_id}/spec-deltas")
async def compute_spec_delta(
    feature_id: uuid.UUID,
    body: ComputeSpecDeltaRequest,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, str]:
    delta = await SpecDeltaService().compute(
        session,
        from_spec_id=body.from_spec_id,
        to_spec_id=body.to_spec_id,
        delivery_cycle_id=body.delivery_cycle_id,
        ctx=ctx,
    )
    return {
        "id": str(delta.id),
        "key": delta.key,
        "content_hash": delta.content_hash,
        "status": delta.status,
    }


@router.get("/spec-deltas/{delta_id}")
async def get_spec_delta(
    delta_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    delta = await SpecDeltaService().get(session, delta_id)
    return {
        "id": str(delta.id),
        "key": delta.key,
        "status": delta.status,
        "content_hash": delta.content_hash,
        "changes": delta.changes,
        "from_spec_id": str(delta.from_spec_id) if delta.from_spec_id else None,
        "to_spec_id": str(delta.to_spec_id),
    }


@router.post("/spec-deltas/{delta_id}/approval-request")
async def request_spec_delta_approval(
    delta_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, str]:
    delta = await SpecDeltaService().request_approval(session, delta_id, ctx)
    return {"id": str(delta.id), "approval_id": str(delta.approval_id)}
