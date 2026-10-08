from __future__ import annotations

import uuid

from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.exceptions import DomainError
from core.orchestrator.models import OrchestratorSession
from core.orchestrator.service import OrchestratorService
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import command_context, get_actor, get_db

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


class CreateSessionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: uuid.UUID | None = None
    delivery_cycle_id: uuid.UUID | None = None


class SessionResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID | None
    delivery_cycle_id: uuid.UUID | None
    turns: list[dict[str, object]]
    expires_at: str


class FocusBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_type: str
    subject_id: uuid.UUID


class TurnBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=8000)
    focus: FocusBody | None = None


def _session_resp(row: OrchestratorSession) -> SessionResponse:
    return SessionResponse(
        id=row.id,
        project_id=row.project_id,
        delivery_cycle_id=row.delivery_cycle_id,
        turns=list(row.turns or []),
        expires_at=row.expires_at.isoformat(),
    )


@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(
    body: CreateSessionBody,
    session: AsyncSession = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> SessionResponse:
    row = await OrchestratorService().create_session(
        session,
        actor_id=actor.id,
        project_id=body.project_id,
        delivery_cycle_id=body.delivery_cycle_id,
    )
    return _session_resp(row)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> SessionResponse:
    try:
        row = await OrchestratorService().get_session(session, session_id, actor.id)
    except ValueError as exc:
        raise DomainError(code="NOT_FOUND", message=str(exc)) from exc
    return _session_resp(row)


@router.post("/sessions/{session_id}/turns")
async def post_turn(
    session_id: uuid.UUID,
    body: TurnBody,
    session: AsyncSession = Depends(get_db),
    actor: Actor = Depends(get_actor),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, str]:
    svc = OrchestratorService()
    try:
        orch = await svc.get_session(session, session_id, actor.id)
    except ValueError as exc:
        raise DomainError(code="NOT_FOUND", message=str(exc)) from exc
    ctx = CommandContext(
        actor=actor,
        correlation_id=ctx.correlation_id,
        idempotency_key=ctx.idempotency_key,
        command_log_id=ctx.command_log_id,
    )
    focus = None
    if body.focus is not None:
        focus = {
            "subject_type": body.focus.subject_type,
            "subject_id": str(body.focus.subject_id),
        }
    try:
        return await svc.append_user_turn(session, orch, body.message, ctx, focus=focus)
    except ValueError as exc:
        raise DomainError(code="INVALID_INPUT", message=str(exc)) from exc
