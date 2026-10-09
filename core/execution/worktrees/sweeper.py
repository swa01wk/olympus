"""Orphan execution workspace cleanup."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.domain.enums import ExecutionWorkspaceState
from core.domain.execution_workspaces.models import ExecutionWorkspace
from core.execution.worktrees.git import GitCli
from core.repositories.workspace_locator import WorkspaceLocator


class WorktreeSweeper:
    def __init__(self, locator: WorkspaceLocator | None = None, git: GitCli | None = None) -> None:
        self._locator = locator or WorkspaceLocator()
        self._git = git or GitCli()

    async def cleanup_orphans(self, session: AsyncSession) -> int:
        removed = 0
        settings = get_settings()
        worktree_root = settings.effective_worktree_root
        projects = worktree_root / "projects"
        if not projects.exists():
            return 0
        active_locations: set[str] = set()
        result = await session.execute(
            select(ExecutionWorkspace.logical_location).where(
                ExecutionWorkspace.state.in_(
                    [
                        ExecutionWorkspaceState.CREATING,
                        ExecutionWorkspaceState.ACTIVE,
                        ExecutionWorkspaceState.RETAINED,
                    ]
                )
            )
        )
        for (loc,) in result.all():
            active_locations.add(loc)

        # An execution runs in one uncommitted transaction, so its workspace row is
        # invisible here until it finishes; only age tells a live worktree from an orphan.
        cutoff = time.time() - settings.worktree_orphan_grace_seconds
        for wt_dir in projects.glob("*/worktrees/*"):
            if not wt_dir.is_dir():
                continue
            rel = str(wt_dir.relative_to(worktree_root))
            if rel in active_locations:
                continue
            if wt_dir.stat().st_mtime > cutoff:
                continue
            self._prune_parent_repo(rel)
            shutil.rmtree(wt_dir, ignore_errors=True)
            removed += 1

        self._global_prune(worktree_root)
        return removed

    def _prune_parent_repo(self, logical_location: str) -> None:
        parts = logical_location.split("/")
        if len(parts) < 4:
            return
        project_id = parts[1]
        repo_logical = f"projects/{project_id}/repo"
        try:
            git_dir = self._locator.resolve("LOCAL_FILESYSTEM", repo_logical)
            self._git.run(
                GitCli.hook_disabled_config_args() + ["worktree", "prune"],
                git_dir=git_dir,
                check=False,
            )
        except ValueError:
            return

    def _global_prune(self, root: Path) -> None:
        for repo in root.glob("projects/*/repo"):
            if repo.is_dir():
                self._git.run(
                    GitCli.hook_disabled_config_args() + ["worktree", "prune"],
                    git_dir=repo,
                    check=False,
                )
