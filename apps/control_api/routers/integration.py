from __future__ import annotations

import uuid

from core.commands.bus import CommandBus, CommandResult
from core.commands.context import CommandContext
from core.integration.models import IntegrationCandidate
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.command_dispatch import dispatch
from apps.control_api.deps import command_context, get_command_bus, get_db
from apps.control_api.schemas.integration import IntegrationCandidateResponse

router = APIRouter(
    prefix="/delivery-cycles/{cycle_id}/integration-candidates", tags=["integration"]
)


@router.post("", status_code=201)
async def create_integration_candidate(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    bus: CommandBus = Depends(get_command_bus),
    ctx: CommandContext = Depends(command_context),
) -> CommandResult:
    return await dispatch(
        session,
        bus,
        name="integration_candidate.create",
        target_type="delivery_cycle",
        target_id=str(cycle_id),
        payload={"cycle_id": str(cycle_id)},
        ctx=ctx,
    )


@router.get("")
async def list_integration_candidates(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[IntegrationCandidateResponse]:
    result = await session.execute(
        select(IntegrationCandidate).where(IntegrationCandidate.delivery_cycle_id == cycle_id)
    )
    return [IntegrationCandidateResponse.from_model(row) for row in result.scalars()]


@router.get("/{ic_id}")
async def get_integration_candidate(
    cycle_id: uuid.UUID,
    ic_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> IntegrationCandidateResponse:
    row = await session.get(IntegrationCandidate, ic_id)
    if row is None or row.delivery_cycle_id != cycle_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Not found")
    return IntegrationCandidateResponse.from_model(row)
