"""Readonly verification workspace with Sentinel overlay (Phase 09 §4)."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.exceptions import DomainError
from core.domain.execution_workspaces.models import ExecutionWorkspace
from core.domain.executions.models import Execution
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.execution.worktrees.git import GitCli, resolve_git_metadata_dir
from core.execution.worktrees.manager import WorktreeManager
from core.integration.models import IntegrationCandidate
from core.repositories.workspace_locator import WorkspaceLocator

OVERLAY_DIR = ".olympus_verification"


class VerificationWorkspaceService:
    def __init__(
        self,
        worktrees: WorktreeManager | None = None,
        locator: WorkspaceLocator | None = None,
        git: GitCli | None = None,
    ) -> None:
        self._worktrees = worktrees or WorktreeManager()
        self._locator = locator or WorkspaceLocator()
        self._git = git or GitCli()

    async def prepare(
        self,
        session: AsyncSession,
        execution: Execution,
        ic_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        correlation_id: str,
    ) -> tuple[ExecutionWorkspace, Path]:
        ic = await session.get(IntegrationCandidate, ic_id)
        if ic is None or ic.integrated_sha is None:
            raise DomainError(code="IC_NOT_READY", message="IC missing integrated SHA")
        repo = await session.get(Repository, ic.repository_id)
        if repo is None or repo.canonical_commit != ic.integrated_sha:
            raise DomainError(
                code="CANONICAL_REVISION_MISMATCH",
                message="Repository canonical commit must match IC integrated SHA",
            )
        cycle = await session.get(DeliveryCycle, ic.delivery_cycle_id)
        if cycle is None:
            raise DomainError(code="NOT_FOUND", message="Delivery cycle not found")
        ws = await self._worktrees.create_readonly(
            session,
            execution,
            ic.repository_id,
            ic.integrated_sha,
            actor_id=actor_id,
            correlation_id=correlation_id,
            project_id=cycle.project_id,
        )
        if repo.workspace_id is None:
            raise DomainError(code="REPOSITORY_NOT_READY", message="Missing workspace")
        canonical_ws = await session.get(RepositoryWorkspace, repo.workspace_id)
        if canonical_ws is None:
            raise DomainError(code="REPOSITORY_NOT_READY", message="Missing workspace row")
        wt_path = self._locator.resolve(canonical_ws.storage_backend, ws.logical_location)
        head = self._git.run(["rev-parse", "HEAD"], cwd=wt_path, check=True).stdout.strip()
        if head != ic.integrated_sha:
            raise DomainError(
                code="CANONICAL_REVISION_MISMATCH",
                message="Verification workspace HEAD mismatch",
            )
        exclude_file = resolve_git_metadata_dir(wt_path) / "info" / "exclude"
        exclude_file.parent.mkdir(parents=True, exist_ok=True)
        existing = exclude_file.read_text(encoding="utf-8") if exclude_file.exists() else ""
        if OVERLAY_DIR not in existing:
            exclude_file.write_text(
                existing.rstrip() + f"\n{OVERLAY_DIR}/\n",
                encoding="utf-8",
            )
        overlay = wt_path / OVERLAY_DIR
        overlay.mkdir(parents=True, exist_ok=True)
        return ws, overlay
