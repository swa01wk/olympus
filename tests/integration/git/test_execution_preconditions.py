from __future__ import annotations

import pytest
from core.commands.context import CommandContext
from core.domain.enums import RepositoryStatus
from core.domain.exceptions import DomainError
from core.domain.execution_workspaces.models import ExecutionWorkspace
from core.domain.projects.models import Project
from core.execution.worktrees.manager import WorktreeManager
from core.repositories.service import RepositoryService
from sqlalchemy import func, select
from tests.fixtures.gateway_harness import seed_gateway_execution


@pytest.mark.git
async def test_worktree_blocked_when_repository_cloning(
    db_session,
    system_ctx: CommandContext,
) -> None:
    project = Project(key="pre-clone", name="Pre")
    db_session.add(project)
    await db_session.flush()
    repo = await RepositoryService().declare_managed(db_session, project.id, system_ctx)
    bundle = await seed_gateway_execution(
        db_session,
        repository=repo,
        base_commit="0" * 40,
        key_prefix="pre",
    )
    mgr = WorktreeManager()
    with pytest.raises(DomainError) as exc:
        await mgr.create(
            db_session,
            bundle.execution,
            repo.id,
            "0" * 40,
            actor_id=system_ctx.actor.id,
            correlation_id="pre",
            project_id=project.id,
        )
    assert exc.value.code == "REPOSITORY_NOT_READY"
    count = await db_session.scalar(
        select(func.count())
        .select_from(ExecutionWorkspace)
        .where(ExecutionWorkspace.execution_id == bundle.execution.id)
    )
    assert count == 0


@pytest.mark.git
async def test_worktree_blocked_when_base_missing(
    db_session,
    system_ctx: CommandContext,
) -> None:
    from core.domain.enums import WorkspaceState as WS
    from core.domain.repositories.models import RepositoryWorkspace
    from core.repositories.materialization import RepositoryMaterializationService

    project = Project(key="pre-base", name="PreBase")
    db_session.add(project)
    await db_session.flush()
    repo = await RepositoryService().declare_managed(db_session, project.id, system_ctx)
    await RepositoryMaterializationService().provision_managed(db_session, repo.id, system_ctx)
    await db_session.refresh(repo)
    workspace = await db_session.get(RepositoryWorkspace, repo.workspace_id)
    assert workspace is not None
    repo.status = RepositoryStatus.READY
    workspace.state = WS.READY
    bundle = await seed_gateway_execution(
        db_session,
        repository=repo,
        base_commit="f" * 40,
        key_prefix="base",
    )
    with pytest.raises(DomainError) as exc:
        await WorktreeManager().create(
            db_session,
            bundle.execution,
            repo.id,
            "f" * 40,
            actor_id=system_ctx.actor.id,
            correlation_id="base",
            project_id=project.id,
        )
    assert exc.value.code == "BASE_COMMIT_UNAVAILABLE"
