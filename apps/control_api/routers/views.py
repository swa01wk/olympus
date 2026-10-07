from __future__ import annotations

import uuid

from core.commands.context import CommandContext
from core.domain.exceptions import DomainError
from core.views.read_models import (
    build_agent_activity_view,
    build_control_plane_view,
    build_cycle_overview,
    build_entity_neighborhood_view,
    build_ic_assurance_view,
    build_inbox_view,
    build_project_coverage_view,
    build_project_overview,
    build_repository_view,
    build_task_dag_view,
)
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import command_context, get_db

router = APIRouter(prefix="/views", tags=["views"])


@router.get("/projects/{project_id}/overview")
async def project_overview(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, object]:
    try:
        return await build_project_overview(session, project_id, ctx)
    except ValueError as exc:
        raise DomainError(code="NOT_FOUND", message=str(exc)) from exc


@router.get("/projects/{project_id}/repository")
async def project_repository_view(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return await build_repository_view(session, project_id)


@router.get("/projects/{project_id}/coverage")
async def project_coverage_view(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return await build_project_coverage_view(session, project_id)


@router.get("/delivery-cycles/{cycle_id}/overview")
async def cycle_overview(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, object]:
    try:
        return await build_cycle_overview(session, cycle_id, ctx)
    except ValueError as exc:
        raise DomainError(code="NOT_FOUND", message=str(exc)) from exc


@router.get("/tasks/{cycle_id}/dag")
async def task_dag_view(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return await build_task_dag_view(session, cycle_id)


@router.get("/code/entities/{stable_key}/neighborhood")
async def entity_neighborhood_view(
    stable_key: str,
    session: AsyncSession = Depends(get_db),
    depth: int = Query(1, ge=1, le=2),
    repository_id: uuid.UUID | None = Query(None),
) -> dict[str, object]:
    return await build_entity_neighborhood_view(
        session, stable_key, depth=depth, repository_id=repository_id
    )


@router.get("/ic/{ic_id}/assurance")
async def ic_assurance_view(
    ic_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return await build_ic_assurance_view(session, ic_id)


@router.get("/inbox")
async def inbox_view(
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> list[dict[str, object]]:
    return await build_inbox_view(session, ctx)


@router.get("/delivery-cycles/{cycle_id}/control-plane")
async def cycle_control_plane_view(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, object]:
    try:
        return await build_control_plane_view(session, cycle_id, ctx)
    except ValueError as exc:
        raise DomainError(code="NOT_FOUND", message=str(exc)) from exc


@router.get("/projects/{project_id}/agent-activity")
async def project_agent_activity_view(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return await build_agent_activity_view(session, project_id)
