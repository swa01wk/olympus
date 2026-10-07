from __future__ import annotations

import uuid

from core.commands.bus import CommandBus
from core.commands.context import CommandContext
from core.domain.approvals.models import Approval
from core.domain.approvals.service import ApprovalService
from core.domain.enums import ApprovalStatus, ApprovalType
from core.domain.exceptions import Unauthorized
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.command_dispatch import dispatch
from apps.control_api.deps import command_context, get_command_bus, get_db

router = APIRouter(prefix="/approvals", tags=["approvals"])


class RequestApprovalBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_type: ApprovalType
    subject_type: str
    subject_id: uuid.UUID
    subject_version: int
    subject_hash: str


class DecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ApprovalStatus
    note: str | None = None


class ApprovalResponse(BaseModel):
    id: uuid.UUID
    key: str
    project_id: uuid.UUID
    delivery_cycle_id: uuid.UUID | None
    approval_type: str
    subject_type: str
    subject_id: uuid.UUID
    subject_version: int
    subject_hash: str
    status: str


def _resp(a: Approval) -> ApprovalResponse:
    return ApprovalResponse(
        id=a.id,
        key=a.key,
        project_id=a.project_id,
        delivery_cycle_id=a.delivery_cycle_id,
        approval_type=a.approval_type.value,
        subject_type=a.subject_type,
        subject_id=a.subject_id,
        subject_version=a.subject_version,
        subject_hash=a.subject_hash,
        status=a.status.value,
    )


@router.get("", response_model=list[ApprovalResponse])
async def list_approvals(
    status: ApprovalStatus | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> list[ApprovalResponse]:
    from sqlalchemy import select

    stmt = select(Approval)
    if status is not None:
        stmt = stmt.where(Approval.status == status)
    result = await session.execute(stmt)
    return [_resp(a) for a in result.scalars()]


@router.get("/pending", response_model=list[ApprovalResponse])
async def pending_approvals(session: AsyncSession = Depends(get_db)) -> list[ApprovalResponse]:
    return await list_approvals(status=ApprovalStatus.PENDING, session=session)


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ApprovalResponse:
    approval = await session.get(Approval, approval_id)
    if approval is None:
        from core.domain.exceptions import DomainError

        raise DomainError(code="NOT_FOUND", message="Approval not found")
    return _resp(approval)


@router.post("/{approval_id}/decision", response_model=ApprovalResponse)
async def decide(
    approval_id: uuid.UUID,
    body: DecisionBody,
    request: Request,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
    bus: CommandBus = Depends(get_command_bus),
) -> ApprovalResponse:
    payload = {
        "approval_id": str(approval_id),
        "decision": body.decision.value,
        "note": body.note,
    }
    svc = ApprovalService()
    try:
        result = await dispatch(
            session,
            bus,
            name="approval.decide",
            target_type="approval",
            target_id=str(approval_id),
            payload=payload,
            ctx=ctx,
        )
    except Unauthorized:
        await svc.record_decision_denied(request.app.state.session_factory, approval_id, ctx)
        raise
    approval = await session.get(Approval, uuid.UUID(result.data["approval_id"]))
    assert approval is not None
    return _resp(approval)
