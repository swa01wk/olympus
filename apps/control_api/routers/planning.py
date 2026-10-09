from __future__ import annotations

import uuid
from typing import NoReturn

from core.commands.context import CommandContext
from core.domain.exceptions import DomainError
from core.planning.architecture.service import ArchitectureService
from core.planning.implementation_specs.service import ImplementationSpecService
from core.planning.models import Architecture, ImplementationSpec, TaskPlanRow
from core.planning.orchestrator import PlanningOrchestrator
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import command_context, get_db

router = APIRouter(tags=["planning"])


class ApprovalRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delivery_cycle_id: uuid.UUID


@router.post("/delivery-cycles/{cycle_id}/architecture/propose")
async def propose_architecture(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, str]:
    return await PlanningOrchestrator().start_architecture_proposal(session, cycle_id, ctx)


@router.get("/projects/{project_id}/architecture")
async def get_project_architecture(
    project_id: uuid.UUID,
    latest: bool = Query(False, description="Newest version of any status, e.g. under review"),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = ArchitectureService()
    arch = await (svc.get_latest if latest else svc.get_approved)(session, project_id)
    if arch is None:
        raise HTTPException(
            status_code=404, detail="No architecture" if latest else "No approved architecture"
        )
    contracts = await ArchitectureService().get_contracts(session, arch.id)
    return {
        "id": str(arch.id),
        "version": arch.version,
        "status": arch.status.value,
        "kind": arch.kind,
        "body": arch.body,
        "contracts": [
            {"key": c.key, "kind": c.kind, "name": c.name, "definition": c.definition}
            for c in contracts
        ],
    }


@router.get("/architectures/{architecture_id}")
async def get_architecture(
    architecture_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    arch = await session.get(Architecture, architecture_id)
    if arch is None:
        raise HTTPException(status_code=404, detail="Not found")
    contracts = await ArchitectureService().get_contracts(session, arch.id)
    return {
        "id": str(arch.id),
        "version": arch.version,
        "status": arch.status.value,
        "kind": arch.kind,
        "body": arch.body,
        "contracts": [
            {"key": c.key, "kind": c.kind, "name": c.name, "definition": c.definition}
            for c in contracts
        ],
    }


@router.post("/architectures/{architecture_id}/approval-request")
async def architecture_approval_request(
    architecture_id: uuid.UUID,
    body: ApprovalRequestBody,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, str]:
    approval_id = await ArchitectureService().request_approval(
        session, architecture_id, body.delivery_cycle_id, ctx
    )
    return {"approval_id": str(approval_id)}


@router.post("/delivery-cycles/{cycle_id}/implementation-specs/generate")
async def generate_implementation_specs(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, object]:
    orch = PlanningOrchestrator()
    tasks = await orch.start_implementation_spec_generation(session, cycle_id, ctx)
    return {"tasks": tasks}


@router.get("/features/{feature_id}/implementation-specs")
async def list_implementation_specs(
    feature_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    rows = await session.execute(
        select(ImplementationSpec)
        .where(ImplementationSpec.feature_spec_id == feature_id)
        .order_by(ImplementationSpec.version)
    )
    return [
        {
            "id": str(r.id),
            "lineage_key": r.lineage_key,
            "version": r.version,
            "status": r.status.value,
        }
        for r in rows.scalars()
    ]


@router.get("/implementation-specs/{spec_id}")
async def get_implementation_spec(
    spec_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    row = await session.get(ImplementationSpec, spec_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "id": str(row.id),
        "lineage_key": row.lineage_key,
        "version": row.version,
        "status": row.status.value,
        "body": row.body,
        "conformance_report": row.conformance_report,
    }


@router.post("/implementation-specs/{spec_id}/approval-request")
async def implementation_spec_approval_request(
    spec_id: uuid.UUID,
    body: ApprovalRequestBody,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, str]:
    approval_id = await ImplementationSpecService().request_approval(
        session, spec_id, body.delivery_cycle_id, ctx
    )
    return {"approval_id": str(approval_id)}


@router.post("/delivery-cycles/{cycle_id}/task-plan/generate")
async def generate_task_plan(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, str]:
    return await PlanningOrchestrator().start_task_plan_generation(session, cycle_id, ctx)


@router.get("/delivery-cycles/{cycle_id}/task-plans")
async def list_task_plans(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    rows = await session.execute(
        select(TaskPlanRow)
        .where(TaskPlanRow.delivery_cycle_id == cycle_id)
        .order_by(TaskPlanRow.created_at.desc())
    )
    return [
        {
            "id": str(r.id),
            "status": r.status,
            "validation_report": r.validation_report,
            "task_count": len((r.body or {}).get("tasks") or []),
        }
        for r in rows.scalars()
    ]


@router.get("/task-plans/{plan_id}")
async def get_task_plan(
    plan_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    row = await session.get(TaskPlanRow, plan_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "id": str(row.id),
        "status": row.status,
        "body": row.body,
        "validation_report": row.validation_report,
    }


@router.post("/task-plans/{plan_id}/commands/accept")
async def accept_task_plan(
    plan_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, object]:
    from core.commands.handlers import handle_approval_decide
    from core.domain.approvals.models import Approval
    from core.domain.canonical_json import sha256_hex
    from core.domain.enums import ActorKind, ActorRole, ApprovalStatus, ApprovalType
    from core.domain.exceptions import Unauthorized

    if ctx.actor.kind != ActorKind.HUMAN or ActorRole.APPROVER not in ctx.actor.roles:
        raise Unauthorized("HUMAN approver required to accept task plan")
    plan_row = await session.get(TaskPlanRow, plan_id)
    if plan_row is None:
        raise HTTPException(status_code=404, detail="Not found")
    subject_hash = sha256_hex(plan_row.body or {})
    pending = (
        await session.execute(
            select(Approval).where(
                Approval.approval_type == ApprovalType.TASK_PLAN,
                Approval.subject_type == "task_plan",
                Approval.subject_id == plan_id,
                Approval.subject_hash == subject_hash,
                Approval.status == ApprovalStatus.PENDING,
            )
        )
    ).scalar_one_or_none()
    if pending is None:
        raise HTTPException(status_code=400, detail="No pending TASK_PLAN approval")
    await handle_approval_decide(
        session,
        ctx,
        {
            "approval_id": str(pending.id),
            "decision": ApprovalStatus.APPROVED.value,
            "note": "Accepted via planning API",
        },
    )
    row = await session.get(TaskPlanRow, plan_id)
    assert row is not None
    return {"id": str(row.id), "status": row.status}


class ArchitectureVersionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: dict[str, object]
    contracts: list[dict[str, object]] | None = None
    note: str | None = None
    delivery_cycle_id: uuid.UUID


class ImplementationSpecVersionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: dict[str, object]
    note: str | None = None
    delivery_cycle_id: uuid.UUID


@router.post("/architectures/{architecture_id}/versions")
async def post_architecture_version(
    architecture_id: uuid.UUID,
    payload: ArchitectureVersionBody,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, object]:
    from core.planning.schemas import ArchitectureBody, ContractDraft

    try:
        body = ArchitectureBody.model_validate(payload.body)
        contracts = (
            [ContractDraft.model_validate(c) for c in payload.contracts]
            if payload.contracts is not None
            else None
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=_validation_errors(exc)) from exc
    try:
        row = await ArchitectureService().create_edited_version(
            session,
            architecture_id=architecture_id,
            body=body,
            contracts=contracts,
            note=payload.note,
            delivery_cycle_id=payload.delivery_cycle_id,
            ctx=ctx,
        )
    except DomainError as exc:
        _raise_edit_error(exc, {"VALIDATION_FAILED"})
    return {"id": str(row.id), "version": row.version, "status": row.status.value}


@router.post("/implementation-specs/{spec_id}/versions")
async def post_implementation_spec_version(
    spec_id: uuid.UUID,
    payload: ImplementationSpecVersionBody,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, object]:
    from core.planning.schemas import ImplementationSpecBody

    try:
        body = ImplementationSpecBody.model_validate(payload.body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=_validation_errors(exc)) from exc
    try:
        row = await ImplementationSpecService().create_edited_version(
            session,
            spec_id=spec_id,
            body=body,
            note=payload.note,
            delivery_cycle_id=payload.delivery_cycle_id,
            ctx=ctx,
        )
    except DomainError as exc:
        _raise_edit_error(exc, {"VALIDATION_FAILED", "ARCHITECTURE_DELTA_REQUIRED"})
    return {"id": str(row.id), "version": row.version, "status": row.status.value}


def _validation_errors(exc: ValidationError) -> dict[str, object]:
    return {
        "errors": [f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()]
    }


def _raise_edit_error(exc: DomainError, validation_codes: set[str]) -> NoReturn:
    if exc.code in validation_codes:
        raise HTTPException(status_code=422, detail=exc.details or exc.message) from exc
    if exc.code == "NOT_FOUND":
        raise HTTPException(status_code=404, detail=exc.message) from exc
    raise exc


@router.get("/delivery-cycles/{cycle_id}/task-dag")
async def task_dag(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    from core.domain.tasks.models import Task, TaskDependency

    tasks = await session.execute(
        select(Task).where(
            Task.delivery_cycle_id == cycle_id,
            Task.origin == "IMPLEMENTATION_PLAN",
        )
    )
    nodes = [
        {"id": str(t.id), "key": t.key, "title": t.title, "status": t.status.value}
        for t in tasks.scalars()
    ]
    deps = await session.execute(
        select(TaskDependency).where(
            TaskDependency.task_id.in_([uuid.UUID(n["id"]) for n in nodes])
        )
    )
    edges = [{"from": str(d.depends_on_task_id), "to": str(d.task_id)} for d in deps.scalars()]
    return {"nodes": nodes, "edges": edges}
