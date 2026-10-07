from __future__ import annotations

import uuid

from core.integration.models import IntegrationCandidate
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import get_db
from apps.control_api.schemas.integration import IntegrationCandidateResponse

router = APIRouter(prefix="/integration-candidates", tags=["integration"])


@router.get("/{ic_id}", response_model=IntegrationCandidateResponse)
async def get_integration_candidate_by_id(
    ic_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> IntegrationCandidateResponse:
    row = await session.get(IntegrationCandidate, ic_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return IntegrationCandidateResponse.from_model(row)
