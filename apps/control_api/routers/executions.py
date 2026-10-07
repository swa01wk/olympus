from __future__ import annotations

import uuid

from core.commands.context import CommandContext
from core.domain.enums import TaskStatus
from core.domain.exceptions import DomainError
from core.domain.executions.models import Execution, ExecutionEvent, ExecutionSnapshot
from core.domain.model_calls.models import ModelCall
from core.domain.tasks.models import Task
from core.execution.snapshots.base_commit import BaseCommitResolver
from core.scheduler.admission import AdmissionService
from core.scheduler.context_loader import load_eligibility_context, load_task_view
from core.scheduler.eligibility import evaluate
from core.scheduler.refs import build_default_registry
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import command_context, get_db

router = APIRouter(tags=["executions"])


class ExecutionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    key: str
    task_id: uuid.UUID
    status: str
    attempt_number: int
    executor_kind: str
    snapshot_hash: str | None
    failure_class: str | None


class EligibilityResponse(BaseModel):
    eligible: bool
    reasons: list[str]


class CancelExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    then: str = "RETURN_TO_READY"


class ModelCallResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    execution_id: uuid.UUID | None
    model_alias: str
    provider: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float | None
    latency_ms: int
    prompt_hash: str | None
    created_at: str


def _execution_response(
    session_row: Execution,
    snapshot: ExecutionSnapshot | None,
) -> ExecutionResponse:
    return ExecutionResponse(
        id=session_row.id,
        key=session_row.key,
        task_id=session_row.task_id,
        status=session_row.status.value,
        attempt_number=session_row.attempt_number,
        executor_kind=session_row.executor_kind,
        snapshot_hash=snapshot.snapshot_hash if snapshot else None,
        failure_class=session_row.failure_class,
    )


@router.post("/tasks/{task_id}/executions", status_code=201, response_model=ExecutionResponse)
async def request_execution(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> ExecutionResponse:
    admission = AdmissionService()
    try:
        execution = await admission.admit_task(session, task_id, ctx)
    except DomainError as exc:
        if exc.code == "NOT_ELIGIBLE":
            raise HTTPException(status_code=409, detail=exc.details) from exc
        raise
    snap = (
        await session.get(ExecutionSnapshot, execution.snapshot_id)
        if execution.snapshot_id
        else None
    )
    return _execution_response(execution, snap)


@router.get("/tasks/{task_id}/eligibility", response_model=EligibilityResponse)
async def task_eligibility(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> EligibilityResponse:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    ctx = await load_eligibility_context(
        session,
        task,
        ref_registry=build_default_registry(),
        base_resolver=BaseCommitResolver(),
    )
    view = await load_task_view(session, task)
    result = evaluate(view, ctx)
    return EligibilityResponse(eligible=result.eligible, reasons=result.reasons)


@router.get("/tasks/{task_id}/executions", response_model=list[ExecutionResponse])
async def list_executions(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[ExecutionResponse]:
    result = await session.execute(select(Execution).where(Execution.task_id == task_id))
    rows: list[ExecutionResponse] = []
    for ex in result.scalars():
        snap = await session.get(ExecutionSnapshot, ex.snapshot_id) if ex.snapshot_id else None
        rows.append(_execution_response(ex, snap))
    return rows


@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ExecutionResponse:
    execution = await session.get(Execution, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    snap = (
        await session.get(ExecutionSnapshot, execution.snapshot_id)
        if execution.snapshot_id
        else None
    )
    return _execution_response(execution, snap)


@router.get("/executions/{execution_id}/snapshot")
async def get_snapshot(
    execution_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    execution = await session.get(Execution, execution_id)
    if execution is None or execution.snapshot_id is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    snap = await session.get(ExecutionSnapshot, execution.snapshot_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return {"snapshot_hash": snap.snapshot_hash, "content": snap.content}


@router.get("/executions/{execution_id}/model-calls", response_model=list[ModelCallResponse])
async def list_model_calls(
    execution_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[ModelCallResponse]:
    execution = await session.get(Execution, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    result = await session.execute(
        select(ModelCall)
        .where(ModelCall.execution_id == execution_id)
        .order_by(ModelCall.created_at)
    )
    rows: list[ModelCallResponse] = []
    for call in result.scalars():
        cost = float(call.cost_usd_estimate) if call.cost_usd_estimate is not None else None
        rows.append(
            ModelCallResponse(
                id=call.id,
                execution_id=call.execution_id,
                model_alias=call.alias,
                provider=call.provider,
                input_tokens=call.input_tokens,
                output_tokens=call.output_tokens,
                cost_usd=cost,
                latency_ms=call.latency_ms,
                prompt_hash=call.prompt_hash,
                created_at=call.created_at.isoformat(),
            )
        )
    return rows


@router.get("/executions/{execution_id}/events")
async def list_events(
    execution_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    result = await session.execute(
        select(ExecutionEvent)
        .where(ExecutionEvent.execution_id == execution_id)
        .order_by(ExecutionEvent.seq)
    )
    return [
        {"seq": e.seq, "type": e.type, "payload": e.payload, "at": e.at.isoformat()}
        for e in result.scalars()
    ]


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(
    execution_id: uuid.UUID,
    body: CancelExecutionRequest,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, str]:
    from core.execution.service import ExecutionService

    execution = await session.get(Execution, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    await ExecutionService().transition(session, execution_id, "cancel", ctx)
    task = await session.get(Task, execution.task_id)
    if task and body.then == "CANCEL_TASK":
        from core.state.transition_service import TransitionService

        await TransitionService().transition(
            session,
            "task",
            task.id,
            task.status.value,
            "cancel_task",
            ctx,
        )
    elif task and task.status == TaskStatus.RUNNING:
        from core.state.transition_service import TransitionService

        await TransitionService().transition(
            session,
            "task",
            task.id,
            TaskStatus.RUNNING.value,
            "fail_retry",
            ctx,
        )
    return {"status": "CANCELLED"}
