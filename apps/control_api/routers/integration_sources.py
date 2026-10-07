from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from core.domain.exceptions import DomainError
from core.integrations.inbound.models import IntegrationSource
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import get_db, require_scope

router = APIRouter(prefix="/integrations/sources", tags=["integrations"])


class RotateSecretRequest(BaseModel):
    new_secret_ref: str = Field(min_length=1, max_length=256)
    grace_hours: int = Field(default=24, ge=1, le=168)


@router.post("/{source_id}/rotate-secret")
async def rotate_source_secret(
    source_id: uuid.UUID,
    body: RotateSecretRequest,
    session: AsyncSession = Depends(get_db),
    _admin: object = Depends(require_scope("admin")),
) -> dict[str, str]:
    source = await session.get(IntegrationSource, source_id)
    if source is None:
        raise DomainError(code="NOT_FOUND", message="Integration source not found")
    now = datetime.now(UTC).replace(tzinfo=None)
    source.secondary_secret_ref = source.secret_ref
    source.secondary_valid_until = now + timedelta(hours=body.grace_hours)
    source.secret_ref = body.new_secret_ref
    await session.flush()
    return {"status": "rotated", "secondary_valid_until": source.secondary_valid_until.isoformat()}
