from __future__ import annotations

import pytest
from core.domain.enums import ExecutionWorkspaceMode
from core.domain.execution_workspaces.models import ExecutionWorkspace
from core.execution.worktrees.manager import WorktreeManager
from core.scheduler.admission import AdmissionService
from sqlalchemy import select
from tests.fixtures.phase04_harness import seed_code_change_task, seed_greenfield_repository

pytestmark = pytest.mark.git


@pytest.mark.asyncio
async def test_admitted_code_change_gets_writable_worktree(
    db_session,
    system_ctx,
) -> None:
    project, repo, sha = await seed_greenfield_repository(db_session, system_ctx, project_key="wr")
    canonical_before = repo.canonical_commit
    fixture = await seed_code_change_task(db_session, system_ctx, project, repo, sha)
    execution = await AdmissionService().admit_task(db_session, fixture.task_id, system_ctx)
    await WorktreeManager().create(
        db_session,
        execution,
        repo.id,
        sha,
        actor_id=system_ctx.actor.id,
        correlation_id="wr",
        project_id=project.id,
    )
    workspace = (
        await db_session.execute(
            select(ExecutionWorkspace).where(ExecutionWorkspace.execution_id == execution.id)
        )
    ).scalar_one()
    assert workspace.mode == ExecutionWorkspaceMode.WRITABLE
    await db_session.refresh(repo)
    assert repo.canonical_commit == canonical_before
