from __future__ import annotations

import uuid
from typing import Any

from core.assurance.models import Finding
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import get_db

router = APIRouter(tags=["findings"])


class FindingResponse(BaseModel):
    id: uuid.UUID
    key: str
    delivery_cycle_id: uuid.UUID
    category: str
    severity: str
    blocking: bool
    title: str
    status: str
    detail: dict[str, Any]


@router.get("/delivery-cycles/{cycle_id}/findings")
async def list_findings(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[FindingResponse]:
    rows = await session.execute(select(Finding).where(Finding.delivery_cycle_id == cycle_id))
    return [
        FindingResponse(
            id=f.id,
            key=f.key,
            delivery_cycle_id=f.delivery_cycle_id,
            category=f.category,
            severity=f.severity.value,
            blocking=f.blocking,
            title=f.title,
            status=f.status.value,
            detail=f.detail,
        )
        for f in rows.scalars()
    ]


@router.get("/findings/{finding_id}")
async def get_finding(
    finding_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> FindingResponse:
    f = await session.get(Finding, finding_id)
    if f is None:
        raise HTTPException(status_code=404, detail="Not found")
    return FindingResponse(
        id=f.id,
        key=f.key,
        delivery_cycle_id=f.delivery_cycle_id,
        category=f.category,
        severity=f.severity.value,
        blocking=f.blocking,
        title=f.title,
        status=f.status.value,
        detail=f.detail,
    )
