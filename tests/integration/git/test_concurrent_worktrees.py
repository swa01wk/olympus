from __future__ import annotations

import pytest
from core.commands.context import CommandContext
from core.domain.enums import RepositoryStatus
from core.domain.projects.models import Project
from core.execution.worktrees.git import GitCli
from core.execution.worktrees.manager import WorktreeManager
from core.repositories.materialization import RepositoryMaterializationService
from core.repositories.service import RepositoryService
from core.repositories.workspace_locator import WorkspaceLocator
from tests.fixtures.gateway_harness import seed_gateway_execution


@pytest.mark.git
async def test_concurrent_writable_worktrees_isolated(
    db_session,
    system_ctx: CommandContext,
) -> None:
    project = Project(key="conc-proj", name="Conc")
    db_session.add(project)
    await db_session.flush()
    repo = await RepositoryService().declare_managed(db_session, project.id, system_ctx)
    await RepositoryMaterializationService().provision_managed(db_session, repo.id, system_ctx)
    await db_session.refresh(repo)
    canonical_before = repo.canonical_commit
    assert canonical_before
    base = canonical_before
    bundle_a = await seed_gateway_execution(
        db_session, repository=repo, base_commit=base, key_prefix="ca"
    )
    bundle_b = await seed_gateway_execution(
        db_session, repository=repo, base_commit=base, key_prefix="cb"
    )
    mgr = WorktreeManager()
    ws_a = await mgr.create(
        db_session,
        bundle_a.execution,
        repo.id,
        base,
        actor_id=system_ctx.actor.id,
        correlation_id="ca",
        project_id=project.id,
    )
    ws_b = await mgr.create(
        db_session,
        bundle_b.execution,
        repo.id,
        base,
        actor_id=system_ctx.actor.id,
        correlation_id="cb",
        project_id=project.id,
    )
    assert ws_a.logical_location != ws_b.logical_location
    assert ws_a.branch != ws_b.branch
    locator = WorkspaceLocator()
    path_a = locator.resolve("LOCAL_FILESYSTEM", ws_a.logical_location)
    path_b = locator.resolve("LOCAL_FILESYSTEM", ws_b.logical_location)
    (path_a / "only_a.txt").write_text("a\n", encoding="utf-8")
    (path_b / "only_b.txt").write_text("b\n", encoding="utf-8")
    assert not (path_a / "only_b.txt").exists()
    assert not (path_b / "only_a.txt").exists()
    view = await RepositoryService().get_view(db_session, repo.id)
    assert view.workspace is not None
    git_dir = locator.resolve("LOCAL_FILESYSTEM", view.workspace.logical_location)
    git = GitCli()
    refs_before = git.run(["for-each-ref", "--format=%(refname)"], git_dir=git_dir).stdout
    await db_session.refresh(repo)
    assert repo.canonical_commit == canonical_before
    assert repo.status == RepositoryStatus.READY
    refs_after = git.run(["for-each-ref", "--format=%(refname)"], git_dir=git_dir).stdout
    assert refs_before == refs_after
