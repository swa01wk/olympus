from __future__ import annotations

from core.policy.policy_service import ensure_policy_version
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import get_db

router = APIRouter(prefix="/policy", tags=["policy"])


@router.get("/current")
async def current_policy(session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    svc = await ensure_policy_version(session)
    row = svc.version_row
    assert row is not None
    return {
        "id": str(row.id),
        "name": row.name,
        "version": row.version,
        "content_hash": row.content_hash,
        "content": row.content,
    }
