from __future__ import annotations

import shutil

import pytest
from core.commands.context import CommandContext
from core.domain.projects.models import Project
from core.execution.worktrees.manager import WorktreeManager
from core.repositories.materialization import RepositoryMaterializationService
from core.repositories.service import RepositoryService
from core.repositories.workspace_locator import WorkspaceLocator
from tests.fixtures.gateway_harness import seed_gateway_execution


@pytest.mark.git
async def test_readonly_worktree_recreated_after_directory_lost(
    db_session,
    system_ctx: CommandContext,
) -> None:
    project = Project(key="reclaim-proj", name="Reclaim")
    db_session.add(project)
    await db_session.flush()
    repo = await RepositoryService().declare_managed(db_session, project.id, system_ctx)
    await RepositoryMaterializationService().provision_managed(db_session, repo.id, system_ctx)
    await db_session.refresh(repo)
    sha = repo.canonical_commit
    assert sha
    bundle = await seed_gateway_execution(
        db_session, repository=repo, base_commit=sha, key_prefix="rc"
    )
    mgr = WorktreeManager()
    first = await mgr.create_readonly(
        db_session,
        bundle.execution,
        repo.id,
        sha,
        actor_id=system_ctx.actor.id,
        correlation_id="rc-1",
        project_id=project.id,
    )
    path = WorkspaceLocator().resolve("LOCAL_FILESYSTEM", first.logical_location)
    # A crashed attempt rolls back its workspace row but leaves git's registration behind.
    await db_session.delete(first)
    await db_session.flush()
    shutil.rmtree(path)

    second = await mgr.create_readonly(
        db_session,
        bundle.execution,
        repo.id,
        sha,
        actor_id=system_ctx.actor.id,
        correlation_id="rc-2",
        project_id=project.id,
    )
    assert second.logical_location == first.logical_location
    assert path.is_dir()
