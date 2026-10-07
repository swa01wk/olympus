from __future__ import annotations

import uuid

from core.ops.invariants import assert_system_invariants
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import get_db, require_scope

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/invariants")
async def get_invariants(
    project_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _admin: object = Depends(require_scope("admin")),
) -> dict[str, object]:
    report = await assert_system_invariants(session, project_id)
    return {
        "ok": report.ok,
        "project_id": str(project_id) if project_id else None,
        "violations": report.violations,
    }
