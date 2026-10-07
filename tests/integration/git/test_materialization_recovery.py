from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from core.commands.context import CommandContext
from core.domain.enums import RepositoryProvider, RepositoryStatus
from core.domain.projects.models import Project
from core.domain.repositories.models import RepositoryRevision, RepositoryWorkspace
from core.execution.worktrees.git import GitCli
from core.integrations.connectors.base import ConnectorAction
from core.integrations.connectors.registry import get_connector_registry
from core.repositories.materialization import RepositoryMaterializationService
from core.repositories.materialization_loop import MaterializationLoop
from core.repositories.service import RepositoryService
from core.repositories.workspace_locator import WorkspaceLocator
from core.state.transition_service import TransitionService
from sqlalchemy import func, select


@pytest.mark.git
async def test_retry_materialization_from_error(
    db_session,
    system_ctx: CommandContext,
) -> None:
    project = Project(key="rec-proj", name="Rec")
    db_session.add(project)
    await db_session.flush()
    repo = await RepositoryService().declare_managed(db_session, project.id, system_ctx)
    await TransitionService().transition(
        db_session,
        "repository",
        repo.id,
        RepositoryStatus.PROVISIONING.value,
        "materialization_failed",
        system_ctx,
        payload={"reason": "simulated failure"},
    )
    await db_session.refresh(repo)
    assert repo.status == RepositoryStatus.ERROR
    mat = RepositoryMaterializationService()
    await mat.retry_materialization(db_session, repo.id, system_ctx)
    await db_session.refresh(repo)
    assert repo.status == RepositoryStatus.PROVISIONING
    await MaterializationLoop().run_once(db_session, system_ctx)
    await db_session.refresh(repo)
    assert repo.status == RepositoryStatus.READY
    assert repo.registered_sha is not None


@pytest.mark.git
async def test_external_clone_adopted_after_crash_before_record(
    db_session,
    system_ctx: CommandContext,
    tmp_path: Path,
) -> None:
    origin = tmp_path / "origin"
    origin.mkdir()
    (origin / "README.md").write_text("origin\n", encoding="utf-8")
    subprocess.run(["git", "init", "-b", "main"], cwd=origin, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=origin, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "init"],
        cwd=origin,
        check=True,
        capture_output=True,
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=origin, check=True, capture_output=True, text=True
    ).stdout.strip()
    project = Project(key="adopt-ext", name="AdoptExt")
    db_session.add(project)
    await db_session.flush()
    repo = await RepositoryService().register_external(
        db_session,
        project.id,
        "ext",
        RepositoryProvider.LOCAL,
        f"file://{origin.resolve()}",
        "main",
        "none:",
        system_ctx,
    )
    workspace = await db_session.get(RepositoryWorkspace, repo.workspace_id)
    assert workspace is not None
    registry = get_connector_registry()
    clone = ConnectorAction(
        connector="git_local",
        action="clone_repository",
        target_resource=workspace.logical_location,
        inputs={
            "logical_location": workspace.logical_location,
            "remote_url": repo.remote_url,
        },
        idempotency_key=f"clone:{repo.id}",
        correlation_id=system_ctx.correlation_id,
        expected_result_schema="CloneResult",
    )
    await registry.execute_with_persistence(db_session, clone, actor_id=system_ctx.actor.id)
    await db_session.refresh(repo)
    assert repo.registered_sha is None
    assert repo.status == RepositoryStatus.CLONING

    await MaterializationLoop().run_once(db_session, system_ctx)
    await db_session.refresh(repo)
    assert repo.status == RepositoryStatus.READY
    assert repo.registered_sha == head
    rev_count = await db_session.scalar(
        select(func.count())
        .select_from(RepositoryRevision)
        .where(RepositoryRevision.repository_id == repo.id)
    )
    assert rev_count == 1


@pytest.mark.git
async def test_corrupted_partial_clone_is_recloned(
    db_session,
    system_ctx: CommandContext,
    tmp_path: Path,
) -> None:
    origin = tmp_path / "origin2"
    origin.mkdir()
    (origin / "README.md").write_text("ok\n", encoding="utf-8")
    subprocess.run(["git", "init", "-b", "main"], cwd=origin, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=origin, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "init"],
        cwd=origin,
        check=True,
        capture_output=True,
    )
    project = Project(key="reclone", name="Reclone")
    db_session.add(project)
    await db_session.flush()
    repo = await RepositoryService().register_external(
        db_session,
        project.id,
        "ext2",
        RepositoryProvider.LOCAL,
        f"file://{origin.resolve()}",
        "main",
        "none:",
        system_ctx,
    )
    workspace = await db_session.get(RepositoryWorkspace, repo.workspace_id)
    assert workspace is not None
    corrupt = WorkspaceLocator().resolve("LOCAL_FILESYSTEM", workspace.logical_location)
    corrupt.mkdir(parents=True, exist_ok=True)
    (corrupt / "not-a-git-repo.txt").write_text("broken\n", encoding="utf-8")

    await MaterializationLoop().run_once(db_session, system_ctx)
    await db_session.refresh(repo)
    assert repo.status == RepositoryStatus.READY
    assert repo.registered_sha is not None
    git = GitCli()
    ls = git.run(["rev-parse", "HEAD"], git_dir=corrupt, check=False)
    assert ls.returncode == 0


@pytest.mark.git
async def test_greenfield_adopts_existing_olympus_baseline(
    db_session,
    system_ctx: CommandContext,
) -> None:
    project = Project(key="adopt-gf", name="AdoptGF")
    db_session.add(project)
    await db_session.flush()
    repo = await RepositoryService().declare_managed(db_session, project.id, system_ctx)
    workspace = await db_session.get(RepositoryWorkspace, repo.workspace_id)
    assert workspace is not None
    registry = get_connector_registry()
    logical = workspace.logical_location
    init = ConnectorAction(
        connector="git_local",
        action="init_repository",
        target_resource=logical,
        inputs={"logical_location": logical, "default_branch": repo.default_branch},
        idempotency_key=f"init:{repo.id}",
        correlation_id=system_ctx.correlation_id,
        expected_result_schema="InitRepositoryResult",
    )
    await registry.execute_with_persistence(db_session, init, actor_id=system_ctx.actor.id)
    baseline = ConnectorAction(
        connector="git_local",
        action="baseline_commit",
        target_resource=logical,
        inputs={
            "logical_location": logical,
            "default_branch": repo.default_branch,
            "files": {
                "README.md": "# managed\n",
                ".gitignore": "*.pyc\n",
                "OLYMPUS.md": "project_key: managed\nThis repository is governed by Olympus.\n",
            },
            "message": "chore: initialize managed repository",
        },
        idempotency_key=f"baseline:{repo.id}",
        correlation_id=system_ctx.correlation_id,
        expected_result_schema="BaselineCommitResult",
    )
    result, _ = await registry.execute_with_persistence(
        db_session, baseline, actor_id=system_ctx.actor.id
    )
    pre_sha = (result.normalized_result or {}).get("sha")
    assert pre_sha
    await db_session.refresh(repo)
    assert repo.registered_sha is None

    await MaterializationLoop().run_once(db_session, system_ctx)
    await db_session.refresh(repo)
    assert repo.status == RepositoryStatus.READY
    assert repo.registered_sha == pre_sha
    rev_count = await db_session.scalar(
        select(func.count())
        .select_from(RepositoryRevision)
        .where(RepositoryRevision.repository_id == repo.id)
    )
    assert rev_count == 1
    git_dir = WorkspaceLocator().resolve("LOCAL_FILESYSTEM", logical)
    log = GitCli().run(["log", "-1", "--oneline", repo.default_branch], git_dir=git_dir)
    assert log.returncode == 0
    assert log.stdout.strip()
