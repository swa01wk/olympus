"""ExecutionWorkspace (git worktree) lifecycle."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.enums import (
    ExecutionWorkspaceMode,
    ExecutionWorkspaceState,
    ExecutionWorkspaceType,
    RepositoryStatus,
    WorkspaceState,
)
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.domain.execution_workspaces.models import ExecutionWorkspace
from core.domain.executions.models import Execution
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.execution.worktrees.git import GitCli
from core.repositories.git_inspect import GitInspector
from core.repositories.workspace_locator import WorkspaceLocator


class WorktreeManager:
    def __init__(
        self,
        locator: WorkspaceLocator | None = None,
        git: GitCli | None = None,
        inspector: GitInspector | None = None,
    ) -> None:
        self._locator = locator or WorkspaceLocator()
        self._git = git or GitCli()
        self._inspector = inspector or GitInspector()

    async def create(
        self,
        session: AsyncSession,
        execution: Execution,
        repository_id: uuid.UUID,
        base_sha: str,
        *,
        actor_id: uuid.UUID,
        correlation_id: str,
        project_id: uuid.UUID,
        branch_name: str | None = None,
    ) -> ExecutionWorkspace:
        repo = await session.get(Repository, repository_id)
        if repo is None or repo.status != RepositoryStatus.READY:
            raise DomainError(code="REPOSITORY_NOT_READY", message="Repository not READY")
        workspace = await session.get(RepositoryWorkspace, repo.workspace_id)
        if workspace is None or workspace.state != WorkspaceState.READY:
            raise DomainError(code="REPOSITORY_NOT_READY", message="Canonical workspace not READY")
        git_dir = self._locator.resolve(workspace.storage_backend, workspace.logical_location)
        if not self._inspector.commit_exists(git_dir, base_sha):
            raise DomainError(
                code="BASE_COMMIT_UNAVAILABLE",
                message="Base SHA not in object store",
            )
        logical = self._locator.execution_location(project_id, execution.key)
        branch = branch_name or f"olympus/{execution.key}"
        row = ExecutionWorkspace(
            execution_id=execution.id,
            repository_id=repository_id,
            workspace_type=ExecutionWorkspaceType.GIT_WORKTREE,
            mode=ExecutionWorkspaceMode.WRITABLE,
            base_commit=base_sha,
            logical_location=logical,
            branch=branch,
            state=ExecutionWorkspaceState.CREATING,
        )
        session.add(row)
        await session.flush()
        wt_path = self._locator.resolve(workspace.storage_backend, logical)
        wt_path.parent.mkdir(parents=True, exist_ok=True)
        self._git.run(
            GitCli.hook_disabled_config_args()
            + ["worktree", "add", "-b", branch, str(wt_path), base_sha],
            git_dir=git_dir,
            check=True,
        )
        row.state = ExecutionWorkspaceState.ACTIVE
        await session.flush()
        from core.execution.worktrees.secret_hook import install_pre_commit_hook

        install_pre_commit_hook(wt_path)
        await append_domain_event(
            session,
            aggregate_type="execution_workspace",
            aggregate_id=row.id,
            event_type="worktree.created",
            payload={
                "execution_id": str(execution.id),
                "logical_location": logical,
                "branch": branch,
                "mode": row.mode.value,
            },
            actor_id=actor_id,
            correlation_id=correlation_id,
            project_id=project_id,
        )
        return row

    async def create_readonly(
        self,
        session: AsyncSession,
        execution: Execution,
        repository_id: uuid.UUID,
        sha: str,
        *,
        actor_id: uuid.UUID,
        correlation_id: str,
        project_id: uuid.UUID,
    ) -> ExecutionWorkspace:
        repo = await session.get(Repository, repository_id)
        if repo is None or repo.status != RepositoryStatus.READY:
            raise DomainError(code="REPOSITORY_NOT_READY", message="Repository not READY")
        workspace = await session.get(RepositoryWorkspace, repo.workspace_id)
        if workspace is None or workspace.state != WorkspaceState.READY:
            raise DomainError(code="REPOSITORY_NOT_READY", message="Canonical workspace not READY")
        git_dir = self._locator.resolve(workspace.storage_backend, workspace.logical_location)
        if not self._inspector.commit_exists(git_dir, sha):
            raise DomainError(code="BASE_COMMIT_UNAVAILABLE", message="SHA not in object store")
        logical = self._locator.execution_location(project_id, execution.key)
        row = ExecutionWorkspace(
            execution_id=execution.id,
            repository_id=repository_id,
            workspace_type=ExecutionWorkspaceType.GIT_WORKTREE,
            mode=ExecutionWorkspaceMode.READONLY,
            base_commit=sha,
            logical_location=logical,
            branch=None,
            state=ExecutionWorkspaceState.CREATING,
        )
        session.add(row)
        await session.flush()
        wt_path = self._locator.resolve(workspace.storage_backend, logical)
        wt_path.parent.mkdir(parents=True, exist_ok=True)
        self._git.run(
            GitCli.hook_disabled_config_args() + ["worktree", "add", "--detach", str(wt_path), sha],
            git_dir=git_dir,
            check=True,
        )
        row.state = ExecutionWorkspaceState.ACTIVE
        await session.flush()
        from core.execution.worktrees.secret_hook import install_pre_commit_hook

        install_pre_commit_hook(wt_path)
        await append_domain_event(
            session,
            aggregate_type="execution_workspace",
            aggregate_id=row.id,
            event_type="worktree.created",
            payload={
                "execution_id": str(execution.id),
                "logical_location": logical,
                "mode": row.mode.value,
            },
            actor_id=actor_id,
            correlation_id=correlation_id,
            project_id=project_id,
        )
        return row

    async def remove(
        self,
        session: AsyncSession,
        workspace_row: ExecutionWorkspace,
        *,
        retain: bool = False,
        actor_id: uuid.UUID | None = None,
    ) -> None:
        if workspace_row.state in {
            ExecutionWorkspaceState.REMOVED,
            ExecutionWorkspaceState.ORPHANED,
        }:
            return
        repo = await session.get(Repository, workspace_row.repository_id)
        if repo is None:
            return
        canonical = await session.get(RepositoryWorkspace, repo.workspace_id)
        if canonical is None:
            return
        git_dir = self._locator.resolve(canonical.storage_backend, canonical.logical_location)
        wt_path = self._locator.resolve(canonical.storage_backend, workspace_row.logical_location)
        self._git.run(
            GitCli.hook_disabled_config_args() + ["worktree", "remove", "--force", str(wt_path)],
            git_dir=git_dir,
            check=False,
        )
        from datetime import UTC, datetime

        if retain:
            workspace_row.state = ExecutionWorkspaceState.RETAINED
        else:
            workspace_row.state = ExecutionWorkspaceState.REMOVED
        workspace_row.removed_at = datetime.now(UTC)
        await session.flush()
        resolved_actor = actor_id
        if resolved_actor is None:
            from sqlalchemy import select

            from core.domain.actors.models import Actor
            from core.domain.enums import ActorKind

            actor_row = await session.execute(
                select(Actor.id).where(Actor.kind == ActorKind.SYSTEM).limit(1)
            )
            resolved_actor = actor_row.scalar_one()
        await append_domain_event(
            session,
            aggregate_type="execution_workspace",
            aggregate_id=workspace_row.id,
            event_type="worktree.removed",
            payload={"execution_id": str(workspace_row.execution_id), "retained": retain},
            actor_id=resolved_actor,
            correlation_id=str(workspace_row.id),
            project_id=repo.project_id,
        )
