from __future__ import annotations

import uuid

from core.domain.integrations.models import ExternalLink
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import get_db

router = APIRouter(tags=["external-links"])


class ExternalLinkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    provider: str
    external_type: str
    external_id: str
    url: str | None


@router.get("/external-links", response_model=list[ExternalLinkResponse])
async def list_external_links(
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[ExternalLinkResponse]:
    q = select(ExternalLink)
    if entity_type:
        q = q.where(ExternalLink.entity_type == entity_type)
    if entity_id:
        q = q.where(ExternalLink.entity_id == entity_id)
    rows = await session.execute(q.order_by(ExternalLink.created_at.desc()))
    return [
        ExternalLinkResponse(
            id=r.id,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            provider=r.provider,
            external_type=r.external_type,
            external_id=r.external_id,
            url=r.url,
        )
        for r in rows.scalars()
    ]
