from __future__ import annotations

import uuid

from core.commands.bus import CommandBus
from core.commands.context import CommandContext
from core.integrations.inbound.service import InboundService
from core.product_model.changes.service import ChangeRequestService
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import command_context, get_command_bus, get_db

router = APIRouter(tags=["changes"])


class ChangeRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    external_ref: str | None = None


class DeclineArchitectureDeltaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str = Field(min_length=1)


@router.post("/projects/{project_id}/change-requests")
async def create_change_request(
    project_id: uuid.UUID,
    body: ChangeRequestCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
    bus: CommandBus = Depends(get_command_bus),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, object]:
    inbound = InboundService(bus)
    raw = {
        "project_id": str(project_id),
        "json_body": body.model_dump(),
        "idempotency_key": idempotency_key or str(uuid.uuid4()),
        "event_id": idempotency_key or str(uuid.uuid4()),
    }
    result = await inbound.receive(session, "change_request_api", raw, ctx)
    return result


@router.get("/projects/{project_id}/change-requests")
async def list_change_requests(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    from core.product_model.changes.models import ChangeRequest

    rows = (
        await session.execute(select(ChangeRequest).where(ChangeRequest.project_id == project_id))
    ).scalars()
    return [
        {
            "id": str(r.id),
            "key": r.key,
            "status": r.status,
            "delivery_cycle_id": str(r.delivery_cycle_id) if r.delivery_cycle_id else None,
            "title": r.title,
        }
        for r in rows
    ]


@router.get("/change-requests/{cr_id}")
async def get_change_request(
    cr_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    cr = await ChangeRequestService().get(session, cr_id)
    return {
        "id": str(cr.id),
        "key": cr.key,
        "status": cr.status,
        "project_id": str(cr.project_id),
        "delivery_cycle_id": str(cr.delivery_cycle_id) if cr.delivery_cycle_id else None,
        "spec_delta_id": str(cr.spec_delta_id) if cr.spec_delta_id else None,
        "resolved_feature_id": str(cr.resolved_feature_id) if cr.resolved_feature_id else None,
    }


@router.get("/delivery-cycles/{cycle_id}/change-interpretation")
async def get_change_interpretation(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    cr = await ChangeRequestService().get_by_cycle(session, cycle_id)
    if cr is None:
        raise HTTPException(404, "Change request not linked")
    return {
        "interpretation": cr.interpretation,
        "candidates": cr.candidate_features or [],
        "status": cr.status,
    }


@router.post("/delivery-cycles/{cycle_id}/change-interpretation/rerun")
async def rerun_change_interpretation(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, str]:
    from core.product_model.changes.orchestrator import FeatureChangeOrchestrator

    result = await FeatureChangeOrchestrator().schedule_change_interpret(session, cycle_id, ctx)
    return result


@router.get("/delivery-cycles/{cycle_id}/spec-delta")
async def get_cycle_spec_delta(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    from core.product_model.specifications.delta import SpecDeltaService

    delta = await SpecDeltaService().latest_approved_for_cycle(session, cycle_id)
    if delta is None:
        cr = await ChangeRequestService().get_by_cycle(session, cycle_id)
        if cr and cr.spec_delta_id:
            delta = await SpecDeltaService().get(session, cr.spec_delta_id)
    if delta is None:
        raise HTTPException(404, "Spec delta not found")
    return {
        "id": str(delta.id),
        "status": delta.status,
        "content_hash": delta.content_hash,
        "changes": delta.changes,
    }


@router.post("/delivery-cycles/{cycle_id}/architecture-delta/decline")
async def decline_architecture_delta(
    cycle_id: uuid.UUID,
    body: DeclineArchitectureDeltaRequest,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, str]:
    from core.domain.approvals.service import ApprovalService
    from core.domain.enums import ApprovalStatus

    approval_id = await ChangeRequestService().decline_architecture_delta(
        session, cycle_id, body.note, ctx
    )
    await ApprovalService().decide(session, approval_id, ApprovalStatus.APPROVED, body.note, ctx)
    return {"approval_id": str(approval_id)}


@router.post("/delivery-cycles/{cycle_id}/architecture-delta/propose")
async def propose_architecture_delta(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, str]:
    from core.product_model.changes.orchestrator import FeatureChangeOrchestrator

    return await FeatureChangeOrchestrator().schedule_architecture_delta(session, cycle_id, ctx)
