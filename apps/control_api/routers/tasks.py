from __future__ import annotations

import uuid

from core.commands.bus import CommandBus
from core.commands.context import CommandContext
from core.domain.enums import TaskOrigin, WorkType
from core.domain.tasks.models import Task
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.command_dispatch import dispatch
from apps.control_api.deps import command_context, get_command_bus, get_db

router = APIRouter(tags=["tasks"])


class CreateTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    work_type: WorkType
    origin: TaskOrigin = TaskOrigin.CONTROL_PLANE
    priority: int = 100


class TaskResponse(BaseModel):
    id: uuid.UUID
    delivery_cycle_id: uuid.UUID
    key: str
    title: str
    work_type: str
    origin: str
    status: str
    priority: int
    blocked_reason: str | None


class DependencyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    depends_on_task_id: uuid.UUID


class TaskCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_state: str


def _task_response(task: Task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        delivery_cycle_id=task.delivery_cycle_id,
        key=task.key,
        title=task.title,
        work_type=task.work_type.value,
        origin=task.origin.value,
        status=task.status.value,
        priority=task.priority,
        blocked_reason=task.blocked_reason,
    )


@router.post("/delivery-cycles/{cycle_id}/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    cycle_id: uuid.UUID,
    body: CreateTaskRequest,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
    bus: CommandBus = Depends(get_command_bus),
) -> TaskResponse:
    payload = body.model_dump(mode="json")
    payload["cycle_id"] = str(cycle_id)
    result = await dispatch(
        session,
        bus,
        name="create_task",
        target_type="delivery_cycle",
        target_id=str(cycle_id),
        payload=payload,
        ctx=ctx,
    )
    task = await session.get(Task, uuid.UUID(result.data["task_id"]))
    assert task is not None
    return _task_response(task)


@router.get("/delivery-cycles/{cycle_id}/tasks", response_model=list[TaskResponse])
async def list_tasks(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[TaskResponse]:
    from sqlalchemy import select

    result = await session.execute(select(Task).where(Task.delivery_cycle_id == cycle_id))
    return [_task_response(t) for t in result.scalars()]


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> TaskResponse:
    task = await session.get(Task, task_id)
    if task is None:
        from core.domain.exceptions import DomainError

        raise DomainError(code="NOT_FOUND", message="Task not found")
    return _task_response(task)


@router.post("/tasks/{task_id}/dependencies", status_code=204)
async def add_dependency(
    task_id: uuid.UUID,
    body: DependencyRequest,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
    bus: CommandBus = Depends(get_command_bus),
) -> None:
    await dispatch(
        session,
        bus,
        name="task.add_dependency",
        target_type="task",
        target_id=str(task_id),
        payload={
            "task_id": str(task_id),
            "depends_on_task_id": str(body.depends_on_task_id),
        },
        ctx=ctx,
    )


@router.post("/tasks/{task_id}/commands/{command_name}")
async def task_command(
    task_id: uuid.UUID,
    command_name: str,
    body: TaskCommandRequest,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
    bus: CommandBus = Depends(get_command_bus),
) -> dict[str, str]:
    payload = {
        "task_id": str(task_id),
        "command_name": command_name,
        "expected_state": body.expected_state,
    }
    result = await dispatch(
        session,
        bus,
        name="task.command",
        target_type="task",
        target_id=str(task_id),
        payload=payload,
        ctx=ctx,
    )
    return result.data
