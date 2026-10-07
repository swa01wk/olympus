from __future__ import annotations

import uuid

from core.commands.context import CommandContext
from core.domain.exceptions import DomainError
from core.domain.integrations.models import ReconciliationItem
from core.integrations.reconciliation.service import ReconciliationService
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import command_context, get_db

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


class ReconciliationItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    key: str
    kind: str
    status: str
    attempts: int
    correlation_id: str


class ResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: str
    note: str | None = None


@router.get("", response_model=list[ReconciliationItemResponse])
async def list_reconciliation(
    session: AsyncSession = Depends(get_db),
) -> list[ReconciliationItemResponse]:
    rows = await session.execute(
        select(ReconciliationItem).order_by(ReconciliationItem.created_at.desc())
    )
    return [
        ReconciliationItemResponse(
            id=r.id,
            key=r.key,
            kind=r.kind,
            status=r.status,
            attempts=r.attempts,
            correlation_id=r.correlation_id,
        )
        for r in rows.scalars()
    ]


@router.get("/{item_id}", response_model=ReconciliationItemResponse)
async def get_reconciliation(
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ReconciliationItemResponse:
    row = await session.get(ReconciliationItem, item_id)
    if row is None:
        raise DomainError(code="NOT_FOUND", message="Not found")
    return ReconciliationItemResponse(
        id=row.id,
        key=row.key,
        kind=row.kind,
        status=row.status,
        attempts=row.attempts,
        correlation_id=row.correlation_id,
    )


@router.post("/{item_id}/retry", response_model=ReconciliationItemResponse)
async def retry_reconciliation(
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> ReconciliationItemResponse:
    row = await ReconciliationService().reconcile_item(session, item_id, ctx)
    await session.commit()
    return ReconciliationItemResponse(
        id=row.id,
        key=row.key,
        kind=row.kind,
        status=row.status,
        attempts=row.attempts,
        correlation_id=row.correlation_id,
    )


@router.post("/{item_id}/resolve", response_model=ReconciliationItemResponse)
async def resolve_reconciliation(
    item_id: uuid.UUID,
    body: ResolveRequest,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> ReconciliationItemResponse:
    row = await session.get(ReconciliationItem, item_id)
    if row is None:
        raise DomainError(code="NOT_FOUND", message="Not found")
    row.status = "RESOLVED_MANUAL"
    row.resolution_note = body.note
    row.resolved_by_actor_id = ctx.actor.id
    await session.commit()
    return ReconciliationItemResponse(
        id=row.id,
        key=row.key,
        kind=row.kind,
        status=row.status,
        attempts=row.attempts,
        correlation_id=row.correlation_id,
    )
