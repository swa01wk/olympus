from __future__ import annotations

import uuid

from core.commands.bus import CommandBus
from core.commands.context import CommandContext
from core.domain.projects.models import Project
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.command_dispatch import dispatch
from apps.control_api.deps import command_context, get_command_bus, get_db

router = APIRouter(prefix="/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    name: str
    description: str | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    description: str | None
    readiness_state: str


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: CreateProjectRequest,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
    bus: CommandBus = Depends(get_command_bus),
) -> Project:
    payload = body.model_dump(mode="json")
    result = await dispatch(
        session,
        bus,
        name="create_project",
        target_type="project",
        target_id=body.key,
        payload=payload,
        ctx=ctx,
    )
    project = await session.get(Project, uuid.UUID(result.data["project_id"]))
    assert project is not None
    return project


@router.get("", response_model=list[ProjectResponse])
async def list_projects(session: AsyncSession = Depends(get_db)) -> list[Project]:
    from sqlalchemy import select

    result = await session.execute(select(Project).order_by(Project.created_at))
    return list(result.scalars())


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        from core.domain.exceptions import DomainError

        raise DomainError(code="NOT_FOUND", message="Project not found")
    return project
