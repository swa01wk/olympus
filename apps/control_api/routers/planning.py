from __future__ import annotations

import uuid

from core.commands.context import CommandContext
from core.planning.architecture.service import ArchitectureService
from core.planning.implementation_specs.service import ImplementationSpecService
from core.planning.models import Architecture, ImplementationSpec, TaskPlanRow
from core.planning.orchestrator import PlanningOrchestrator
from core.planning.task_plans.service import TaskPlanService
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
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
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    arch = await ArchitectureService().get_approved(session, project_id)
    if arch is None:
        raise HTTPException(status_code=404, detail="No approved architecture")
    contracts = await ArchitectureService().get_contracts(session, arch.id)
    return {
        "id": str(arch.id),
        "version": arch.version,
        "status": arch.status.value,
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
    row = await TaskPlanService().accept(session, plan_id, ctx)
    return {"id": str(row.id), "status": row.status}


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
