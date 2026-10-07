import pytest
from core.commands.context import CommandContext
from core.domain.enums import RepositoryStatus, WorkspaceState
from core.domain.projects.models import Project
from core.execution.worktrees.git import GitCli
from core.repositories.materialization import RepositoryMaterializationService
from core.repositories.service import RepositoryService
from core.repositories.workspace_locator import WorkspaceLocator


@pytest.mark.git
async def test_greenfield_provisioning(db_session, system_ctx: CommandContext) -> None:
    project = Project(key="PRJ-0001", name="greenfield")
    db_session.add(project)
    await db_session.flush()
    svc = RepositoryService()
    repo = await svc.declare_managed(db_session, project.id, system_ctx)
    mat = RepositoryMaterializationService()
    await mat.provision_managed(db_session, repo.id, system_ctx)
    await db_session.refresh(repo)
    assert repo.status == RepositoryStatus.READY
    assert repo.canonical_commit is not None
    view = await svc.get_view(db_session, repo.id)
    assert view.workspace is not None
    assert view.workspace.state == WorkspaceState.READY
    locator = WorkspaceLocator()
    git_dir = locator.resolve("LOCAL_FILESYSTEM", view.workspace.logical_location)
    git = GitCli()
    ls = git.run(["ls-tree", "--name-only", repo.default_branch], git_dir=git_dir)
    tree = ls.stdout.splitlines()
    assert set(tree) == {"README.md", ".gitignore", "OLYMPUS.md"}
