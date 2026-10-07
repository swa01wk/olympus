from __future__ import annotations

import uuid

from core.domain.audit.models import AuditEvent
from core.security.audit_chain import verify_project_chain
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import get_db, require_scope

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def query_audit(
    target_type: str = Query(...),
    target_id: str = Query(...),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    from sqlalchemy import select

    result = await session.execute(
        select(AuditEvent)
        .where(AuditEvent.target_type == target_type, AuditEvent.target_id == target_id)
        .order_by(AuditEvent.occurred_at)
    )
    return [
        {
            "id": str(row.id),
            "action": row.action,
            "actor_id": str(row.actor_id),
            "before": row.before,
            "after": row.after,
            "occurred_at": row.occurred_at.isoformat(),
        }
        for row in result.scalars()
    ]


@router.get("/verify")
async def verify_audit_chain(
    project_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _reader: object = Depends(require_scope("read")),
) -> dict[str, object]:
    report = await verify_project_chain(session, project_id)
    return {
        "valid": report.valid,
        "project_id": str(project_id) if project_id else None,
        "rows_checked": report.rows_checked,
        "first_invalid_seq": report.first_invalid_seq,
        "message": report.message,
    }
