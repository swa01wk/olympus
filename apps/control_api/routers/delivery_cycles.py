from __future__ import annotations

import uuid

from core.commands.bus import CommandBus
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import ApprovalType, DeliveryCycleType
from core.domain.exceptions import IllegalTransition, StateConflict
from core.state.preview import TransitionPreviewService, preview_to_api
from core.state.transition_service import TransitionService
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.command_dispatch import dispatch
from apps.control_api.deps import command_context, get_command_bus, get_db

router = APIRouter(tags=["delivery-cycles"])


class CreateCycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: DeliveryCycleType
    objective: str
    repository_id: uuid.UUID | None = None


class CycleResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    key: str
    type: str
    objective: str
    state: str
    state_version: int
    repository_id: uuid.UUID | None
    base_sha: str | None
    allowed_commands: list[dict[str, object]] = []


class CycleCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_state: str
    payload: dict[str, object] | None = None


class RequestApprovalBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_type: ApprovalType
    subject_type: str
    subject_id: uuid.UUID
    subject_version: int
    subject_hash: str


@router.post(
    "/projects/{project_id}/delivery-cycles", response_model=CycleResponse, status_code=201
)
async def create_cycle(
    project_id: uuid.UUID,
    body: CreateCycleRequest,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
    bus: CommandBus = Depends(get_command_bus),
) -> CycleResponse:
    payload = body.model_dump(mode="json")
    payload["project_id"] = str(project_id)
    result = await dispatch(
        session,
        bus,
        name="create_delivery_cycle",
        target_type="project",
        target_id=str(project_id),
        payload=payload,
        ctx=ctx,
    )
    cycle = await session.get(DeliveryCycle, uuid.UUID(result.data["cycle_id"]))
    assert cycle is not None
    svc = DeliveryCycleService()
    allowed = await svc.allowed_commands(session, cycle, ctx)
    return CycleResponse(
        id=cycle.id,
        project_id=cycle.project_id,
        key=cycle.key,
        type=cycle.type.value,
        objective=cycle.objective,
        state=cycle.state,
        state_version=cycle.state_version,
        repository_id=cycle.repository_id,
        base_sha=cycle.base_sha,
        allowed_commands=allowed,
    )


@router.get("/projects/{project_id}/delivery-cycles", response_model=list[CycleResponse])
async def list_cycles(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> list[CycleResponse]:
    from sqlalchemy import select

    svc = DeliveryCycleService()
    result = await session.execute(
        select(DeliveryCycle).where(DeliveryCycle.project_id == project_id)
    )
    out: list[CycleResponse] = []
    for cycle in result.scalars():
        allowed = await svc.allowed_commands(session, cycle, ctx)
        out.append(
            CycleResponse(
                id=cycle.id,
                project_id=cycle.project_id,
                key=cycle.key,
                type=cycle.type.value,
                objective=cycle.objective,
                state=cycle.state,
                state_version=cycle.state_version,
                repository_id=cycle.repository_id,
                base_sha=cycle.base_sha,
                allowed_commands=allowed,
            )
        )
    return out


@router.get("/delivery-cycles/{cycle_id}/next-transitions")
async def next_transitions(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> list[dict[str, object]]:
    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None:
        from core.domain.exceptions import DomainError

        raise DomainError(code="NOT_FOUND", message="Delivery cycle not found")
    previews = await TransitionPreviewService().preview_delivery_cycle(session, cycle, ctx)
    return [preview_to_api(p) for p in previews]


@router.get("/delivery-cycles/{cycle_id}", response_model=CycleResponse)
async def get_cycle(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> CycleResponse:
    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None:
        from core.domain.exceptions import DomainError

        raise DomainError(code="NOT_FOUND", message="Delivery cycle not found")
    allowed = await DeliveryCycleService().allowed_commands(session, cycle, ctx)
    return CycleResponse(
        id=cycle.id,
        project_id=cycle.project_id,
        key=cycle.key,
        type=cycle.type.value,
        objective=cycle.objective,
        state=cycle.state,
        state_version=cycle.state_version,
        repository_id=cycle.repository_id,
        base_sha=cycle.base_sha,
        allowed_commands=allowed,
    )


@router.post("/delivery-cycles/{cycle_id}/approvals", status_code=201)
async def request_approval(
    cycle_id: uuid.UUID,
    body: RequestApprovalBody,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
    bus: CommandBus = Depends(get_command_bus),
) -> dict[str, object]:
    payload = body.model_dump(mode="json")
    payload["cycle_id"] = str(cycle_id)
    result = await dispatch(
        session,
        bus,
        name="approval.request",
        target_type="delivery_cycle",
        target_id=str(cycle_id),
        payload=payload,
        ctx=ctx,
    )
    data = result.data
    return {
        "id": data.get("approval_id", data.get("id")),
        "key": data["key"],
        "status": data["status"],
    }


@router.post("/delivery-cycles/{cycle_id}/commands/{command_name}")
async def cycle_command(
    cycle_id: uuid.UUID,
    command_name: str,
    body: CycleCommandRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
    bus: CommandBus = Depends(get_command_bus),
) -> dict[str, object]:
    payload = {
        "cycle_id": str(cycle_id),
        "command_name": command_name,
        "expected_state": body.expected_state,
        "payload": body.payload,
    }
    try:
        result = await dispatch(
            session,
            bus,
            name="delivery_cycle.transition",
            target_type="delivery_cycle",
            target_id=str(cycle_id),
            payload=payload,
            ctx=ctx,
        )
    except (StateConflict, IllegalTransition) as exc:
        factory = request.app.state.session_factory
        await TransitionService().record_rejection(
            factory,
            aggregate="delivery_cycle",
            aggregate_id=cycle_id,
            command=command_name,
            reason=exc.code,
            ctx=ctx,
        )
        raise exc
    return result.data
