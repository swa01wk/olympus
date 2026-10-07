from __future__ import annotations

import uuid

from core.domain.actions.models import ActionRequest, ActionResult
from core.domain.exceptions import DomainError
from core.domain.executions.models import Execution, ExecutionLease
from core.tools.gateway import ToolGateway
from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import get_db
from apps.control_api.deps_execution_token import execution_scoped_token

router = APIRouter(tags=["actions"])


class InvokeActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    params: dict[str, object] = Field(default_factory=dict)
    idempotency_key: str | None = None


class ActionRequestResponse(BaseModel):
    id: uuid.UUID
    key: str
    execution_id: uuid.UUID | None
    tool: str
    resource: str
    action: str
    status: str
    policy_decision: dict[str, object] | None
    approval_id: uuid.UUID | None
    result_status: str | None
    result_output: dict[str, object] | None
    denial_reasons: list[str] | None


def _action_response(
    req: ActionRequest,
    result: ActionResult | None,
    *,
    extra_denial: list[str] | None = None,
) -> ActionRequestResponse:
    denial: list[str] | None = extra_denial
    reasons = req.policy_decision.get("reasons") if req.policy_decision else None
    if denial is None and isinstance(reasons, list):
        denial = [str(x) for x in reasons]
    return ActionRequestResponse(
        id=req.id,
        key=req.key,
        execution_id=req.execution_id,
        tool=req.tool,
        resource=req.resource,
        action=req.action,
        status=req.status.value,
        policy_decision=req.policy_decision,
        approval_id=req.approval_id,
        result_status=result.status if result else None,
        result_output=result.output if result else None,
        denial_reasons=denial,
    )


async def _load_result(session: AsyncSession, action_id: uuid.UUID) -> ActionResult | None:
    row = await session.execute(
        select(ActionResult).where(ActionResult.action_request_id == action_id)
    )
    return row.scalar_one_or_none()


@router.post("/executions/{execution_id}/actions", response_model=ActionRequestResponse)
async def invoke_action(
    execution_id: uuid.UUID,
    body: InvokeActionRequest,
    authorization: str = Header(alias="Authorization"),
    token_ctx: tuple[Execution, ExecutionLease] = Depends(execution_scoped_token),
    session: AsyncSession = Depends(get_db),
) -> ActionRequestResponse:
    execution, _lease = token_ctx
    if execution.id != execution_id:
        raise DomainError(code="NOT_FOUND", message="Execution mismatch")
    token = authorization.removeprefix("Bearer ").strip()
    gateway = ToolGateway(session)
    gateway_result = await gateway.handle(
        token,
        body.tool,
        dict(body.params),
        body.idempotency_key,
    )
    req = await session.get(ActionRequest, gateway_result.action_request_id)
    if req is None:
        raise DomainError(code="NOT_FOUND", message="ActionRequest missing after handle")
    result = await _load_result(session, req.id)
    return _action_response(req, result, extra_denial=gateway_result.denial_reasons)


@router.get("/executions/{execution_id}/actions", response_model=list[ActionRequestResponse])
async def list_execution_actions(
    execution_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[ActionRequestResponse]:
    rows = await session.execute(
        select(ActionRequest)
        .where(ActionRequest.execution_id == execution_id)
        .order_by(ActionRequest.created_at)
    )
    out: list[ActionRequestResponse] = []
    for req in rows.scalars():
        out.append(_action_response(req, await _load_result(session, req.id)))
    return out


@router.get("/actions/{action_id}", response_model=ActionRequestResponse)
async def get_action(
    action_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ActionRequestResponse:
    req = await session.get(ActionRequest, action_id)
    if req is None:
        raise DomainError(code="NOT_FOUND", message="Action not found")
    return _action_response(req, await _load_result(session, req.id))
