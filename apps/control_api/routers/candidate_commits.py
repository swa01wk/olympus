from __future__ import annotations

import uuid

from core.domain.candidate_commits.models import CandidateCommit
from core.domain.exceptions import DomainError
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import get_db

router = APIRouter(tags=["candidate_commits"])


class CandidateCommitResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    key: str
    execution_id: uuid.UUID
    task_id: uuid.UUID
    repository_id: uuid.UUID
    branch: str
    sha: str
    parent_sha: str
    base_sha: str
    changed_files: list[dict[str, object]]
    diff_artifact_id: uuid.UUID | None
    created_at: str


def _to_response(row: CandidateCommit) -> CandidateCommitResponse:
    return CandidateCommitResponse(
        id=row.id,
        key=row.key,
        execution_id=row.execution_id,
        task_id=row.task_id,
        repository_id=row.repository_id,
        branch=row.branch,
        sha=row.sha,
        parent_sha=row.parent_sha,
        base_sha=row.base_sha,
        changed_files=list(row.changed_files or []),
        diff_artifact_id=row.diff_artifact_id,
        created_at=row.created_at.isoformat(),
    )


@router.get("/executions/{execution_id}/candidate-commit", response_model=CandidateCommitResponse)
async def get_execution_candidate_commit(
    execution_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> CandidateCommitResponse:
    result = await session.execute(
        select(CandidateCommit).where(CandidateCommit.execution_id == execution_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise DomainError(code="NOT_FOUND", message="No candidate commit for execution")
    return _to_response(row)


@router.get("/candidate-commits/{candidate_commit_id}", response_model=CandidateCommitResponse)
async def get_candidate_commit(
    candidate_commit_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> CandidateCommitResponse:
    row = await session.get(CandidateCommit, candidate_commit_id)
    if row is None:
        raise DomainError(code="NOT_FOUND", message="Candidate commit not found")
    return _to_response(row)
