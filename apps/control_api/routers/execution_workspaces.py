from __future__ import annotations

import uuid

from core.domain.exceptions import DomainError
from core.domain.execution_workspaces.models import ExecutionWorkspace
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import get_db

router = APIRouter(tags=["execution_workspaces"])


class ExecutionWorkspaceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    execution_id: uuid.UUID
    repository_id: uuid.UUID
    workspace_type: str
    mode: str
    base_commit: str
    logical_location: str
    branch: str | None
    state: str


def _to_response(row: ExecutionWorkspace) -> ExecutionWorkspaceResponse:
    return ExecutionWorkspaceResponse(
        id=row.id,
        execution_id=row.execution_id,
        repository_id=row.repository_id,
        workspace_type=row.workspace_type.value,
        mode=row.mode.value,
        base_commit=row.base_commit,
        logical_location=row.logical_location,
        branch=row.branch,
        state=row.state.value,
    )


@router.get(
    "/executions/{execution_id}/workspace",
    response_model=ExecutionWorkspaceResponse,
)
@router.get(
    "/executions/{execution_id}/worktree",
    response_model=ExecutionWorkspaceResponse,
)
async def get_execution_workspace(
    execution_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ExecutionWorkspaceResponse:
    result = await session.execute(
        select(ExecutionWorkspace).where(ExecutionWorkspace.execution_id == execution_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise DomainError(code="NOT_FOUND", message="Execution workspace not found")
    return _to_response(row)
