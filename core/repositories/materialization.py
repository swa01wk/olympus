"""Repository materialization — Greenfield provision and external clone."""

from __future__ import annotations

import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.enums import (
    MaterializationAttemptStatus,
    MaterializationKind,
    RepositorySourceType,
    WorkspaceState,
)
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.domain.repositories.materializations import RepositoryMaterialization
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.integrations.connectors.base import ConnectorAction
from core.integrations.connectors.registry import get_connector_registry
from core.policy.policy_service import load_policy_file
from core.repositories.credentials import build_default_credential_resolver
from core.repositories.git_inspect import GitInspector
from core.repositories.service import RepositoryService
from core.repositories.workspace_locator import WorkspaceLocator


class RepositoryMaterializationService:
    def __init__(
        self,
        locator: WorkspaceLocator | None = None,
    ) -> None:
        self._locator = locator or WorkspaceLocator()
        self._credentials = build_default_credential_resolver()
        self._repos = RepositoryService(locator=self._locator)
        self._inspector = GitInspector()

    async def provision_managed(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        ctx: CommandContext,
    ) -> None:
        repo = await session.get(Repository, repository_id)
        if repo is None or repo.source_type != RepositorySourceType.GREENFIELD_MANAGED:
            raise DomainError(code="INVALID_REPOSITORY", message="Not GREENFIELD_MANAGED")
        workspace = await self._workspace_row(session, repo)
        logical = workspace.logical_location
        registry = get_connector_registry()
        attempt = await self._begin_attempt(session, repo.id, MaterializationKind.PROVISION)
        try:
            adopted = await self.resolve_materialization_head(session, repository_id)
            if adopted is not None and await self._has_olympus_baseline_marker(
                session, repo, adopted[0]
            ):
                sha, branch = adopted
                await self._repos.record_materialization(session, repository_id, sha, branch, ctx)
                workspace.state = WorkspaceState.READY
                workspace.materialized_commit = sha
                attempt.status = MaterializationAttemptStatus.SUCCEEDED
                attempt.resulting_sha = sha
                attempt.observed_default_branch = branch
                attempt.finished_at = datetime.now(UTC)
                await append_domain_event(
                    session,
                    aggregate_type="repository",
                    aggregate_id=repository_id,
                    event_type="repository.materialized",
                    payload={
                        "repository_id": str(repository_id),
                        "source_type": repo.source_type.value,
                        "sha": sha,
                        "default_branch": branch,
                        "adopted": True,
                    },
                    actor_id=ctx.actor.id,
                    correlation_id=ctx.correlation_id,
                    project_id=repo.project_id,
                )
                return
            init_action = ConnectorAction(
                connector="git_local",
                action="init_repository",
                target_resource=logical,
                inputs={"logical_location": logical, "default_branch": repo.default_branch},
                idempotency_key=f"init:{repo.id}",
                correlation_id=ctx.correlation_id,
                expected_result_schema="InitRepositoryResult",
            )
            await registry.execute_with_persistence(session, init_action, actor_id=ctx.actor.id)
            files = {
                "README.md": f"# {repo.name}\n\nManaged by Olympus.\n",
                ".gitignore": "__pycache__/\n.venv/\n*.pyc\n.pytest_cache/\n",
                "OLYMPUS.md": (
                    f"project_key: {repo.name}\nThis repository is governed by Olympus.\n"
                ),
            }
            baseline = ConnectorAction(
                connector="git_local",
                action="baseline_commit",
                target_resource=logical,
                inputs={
                    "logical_location": logical,
                    "default_branch": repo.default_branch,
                    "files": files,
                    "message": f"chore: initialize {repo.name} repository",
                },
                idempotency_key=f"baseline:{repo.id}",
                correlation_id=ctx.correlation_id,
                expected_result_schema="BaselineCommitResult",
            )
            result, _ = await registry.execute_with_persistence(
                session, baseline, actor_id=ctx.actor.id
            )
            sha_raw = (result.normalized_result or {}).get("sha")
            if not isinstance(sha_raw, str) or not sha_raw:
                raise DomainError(code="MATERIALIZATION_FAILED", message="No baseline SHA")
            sha = sha_raw
            await self._repos.record_materialization(
                session, repository_id, sha, repo.default_branch, ctx
            )
            workspace.state = WorkspaceState.READY
            workspace.materialized_commit = sha
            attempt.status = MaterializationAttemptStatus.SUCCEEDED
            attempt.resulting_sha = sha
            attempt.finished_at = datetime.now(UTC)
            await append_domain_event(
                session,
                aggregate_type="repository",
                aggregate_id=repository_id,
                event_type="repository.materialized",
                payload={
                    "repository_id": str(repository_id),
                    "source_type": repo.source_type.value,
                    "sha": sha,
                    "default_branch": repo.default_branch,
                },
                actor_id=ctx.actor.id,
                correlation_id=ctx.correlation_id,
                project_id=repo.project_id,
            )
        except Exception as exc:
            await self._fail_attempt(session, repo, attempt, exc, ctx)

    async def materialize_external(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        ctx: CommandContext,
    ) -> None:
        repo = await session.get(Repository, repository_id)
        if repo is None or repo.source_type != RepositorySourceType.EXTERNAL_CLONE:
            raise DomainError(code="INVALID_REPOSITORY", message="Not EXTERNAL_CLONE")
        if not repo.remote_url:
            raise DomainError(code="INVALID_REMOTE_URL", message="remote_url required")
        workspace = await self._workspace_row(session, repo)
        logical = workspace.logical_location
        registry = get_connector_registry()
        attempt = await self._begin_attempt(session, repo.id, MaterializationKind.CLONE)
        from core.domain.enums import RepositoryProvider
        from core.integrations.connectors.secrets import build_credential_resolver

        cred_resolver = build_credential_resolver(session)
        cred = await cred_resolver.resolve_async(repo.credential_ref)
        try:
            if repo.provider == RepositoryProvider.LOCAL:
                clone_connector = "git_local"
                clone_action = "clone_repository"
            else:
                clone_connector = f"git_provider_{repo.provider.value.lower()}"
                clone_action = "clone"
            clone = ConnectorAction(
                connector=clone_connector,
                action=clone_action,
                target_resource=logical,
                inputs={
                    "logical_location": logical,
                    "remote_url": repo.remote_url,
                    "_credential": cred,
                },
                idempotency_key=f"clone:{repo.id}",
                correlation_id=ctx.correlation_id,
                expected_result_schema="CloneResult",
            )
            await registry.execute_with_persistence(session, clone, actor_id=ctx.actor.id)
            branch_action = ConnectorAction(
                connector="git_local",
                action="resolve_branch",
                target_resource=logical,
                inputs={
                    "logical_location": logical,
                    "requested_branch": (
                        repo.default_branch if repo.default_branch != "main" else None
                    ),
                },
                idempotency_key=f"branch:{repo.id}",
                correlation_id=ctx.correlation_id,
                expected_result_schema="BranchResult",
            )
            branch_result, _ = await registry.execute_with_persistence(
                session, branch_action, actor_id=ctx.actor.id
            )
            branch = (branch_result.normalized_result or {}).get("branch", repo.default_branch)
            if repo.default_branch != branch:
                repo.default_branch = branch
            head_action = ConnectorAction(
                connector="git_local",
                action="resolve_head",
                target_resource=logical,
                inputs={"logical_location": logical, "branch": branch},
                idempotency_key=f"head:{repo.id}:{branch}",
                correlation_id=ctx.correlation_id,
                expected_result_schema="HeadResult",
            )
            head_result, _ = await registry.execute_with_persistence(
                session, head_action, actor_id=ctx.actor.id
            )
            head_sha = (head_result.normalized_result or {}).get("sha")
            if not head_sha:
                raise DomainError(code="MATERIALIZATION_FAILED", message="Cannot resolve HEAD")
            verify = ConnectorAction(
                connector="git_local",
                action="verify_repository",
                target_resource=logical,
                inputs={"logical_location": logical, "sha": head_sha},
                idempotency_key=f"verify:{repo.id}:{head_sha}",
                correlation_id=ctx.correlation_id,
                expected_result_schema="VerifyResult",
            )
            await registry.execute_with_persistence(session, verify, actor_id=ctx.actor.id)
            meta_action = ConnectorAction(
                connector="git_local",
                action="read_metadata",
                target_resource=logical,
                inputs={"logical_location": logical, "sha": head_sha},
                idempotency_key=f"meta:{repo.id}",
                correlation_id=ctx.correlation_id,
                expected_result_schema="MetadataResult",
            )
            meta_result, _ = await registry.execute_with_persistence(
                session, meta_action, actor_id=ctx.actor.id
            )
            meta = meta_result.normalized_result or {}
            policy = load_policy_file().get("repository", {}).get("materialization", {})
            if meta.get("has_submodules") and policy.get("submodules") == "DENY":
                raise DomainError(code="SUBMODULES_DENIED", message="Submodules not allowed")
            max_mb = int(policy.get("max_size_mb", 512))
            size_kb = int(meta.get("size_kb", 0))
            if size_kb > max_mb * 1024:
                raise DomainError(
                    code="REPOSITORY_TOO_LARGE",
                    message="Repository exceeds max_size_mb",
                )
            await self._repos.record_materialization(session, repository_id, head_sha, branch, ctx)
            workspace.state = WorkspaceState.READY
            workspace.materialized_commit = head_sha
            attempt.status = MaterializationAttemptStatus.SUCCEEDED
            attempt.resulting_sha = head_sha
            attempt.observed_default_branch = branch
            attempt.finished_at = datetime.now(UTC)
            await append_domain_event(
                session,
                aggregate_type="repository",
                aggregate_id=repository_id,
                event_type="repository.materialized",
                payload={
                    "repository_id": str(repository_id),
                    "source_type": repo.source_type.value,
                    "sha": head_sha,
                    "default_branch": branch,
                },
                actor_id=ctx.actor.id,
                correlation_id=ctx.correlation_id,
                project_id=repo.project_id,
            )
        except Exception as exc:
            await self._fail_attempt(session, repo, attempt, exc, ctx)

    async def retry_materialization(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        ctx: CommandContext,
    ) -> Repository:
        from core.domain.enums import RepositoryStatus

        repo = await session.get(Repository, repository_id)
        if repo is None:
            raise DomainError(code="NOT_FOUND", message="Repository not found")
        if repo.status != RepositoryStatus.ERROR:
            raise DomainError(
                code="INVALID_STATE",
                message="retry_materialization requires Repository ERROR",
            )
        await self._repos.transitions.transition(
            session,
            "repository",
            repository_id,
            RepositoryStatus.ERROR.value,
            "retry_materialization",
            ctx,
        )
        await session.refresh(repo)
        if repo.source_type == RepositorySourceType.EXTERNAL_CLONE:
            repo.status = RepositoryStatus.CLONING
        repo.status_reason = None
        if repo.workspace_id:
            workspace = await session.get(RepositoryWorkspace, repo.workspace_id)
            if workspace is not None:
                workspace.state = WorkspaceState.PENDING
        await append_domain_event(
            session,
            aggregate_type="repository",
            aggregate_id=repository_id,
            event_type="repository.materialization_started",
            payload={"repository_id": str(repository_id), "retry": True},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=repo.project_id,
        )
        return repo

    async def verify_workspace(self, session: AsyncSession, repository_id: uuid.UUID) -> bool:
        return await self.resolve_materialization_head(session, repository_id) is not None

    async def resolve_materialization_head(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
    ) -> tuple[str, str] | None:
        repo = await session.get(Repository, repository_id)
        if repo is None or repo.workspace_id is None:
            return None
        workspace = await session.get(RepositoryWorkspace, repo.workspace_id)
        if workspace is None:
            return None
        path = self._locator.resolve(workspace.storage_backend, workspace.logical_location)
        if not path.exists():
            return None
        branch = repo.default_branch or "main"
        sha: str | None = None
        for ref in (
            f"refs/heads/{branch}",
            f"refs/remotes/origin/{branch}",
            branch,
        ):
            try:
                sha = self._inspector.resolve_ref(path, ref)
                break
            except ValueError:
                continue
        if sha is None:
            sym = self._git_run_symbolic_head(path)
            if sym is not None:
                branch, sha = sym
        if sha is None or not self._inspector.commit_exists(path, sha):
            return None
        if repo.canonical_commit is not None and not self._inspector.commit_exists(
            path, repo.canonical_commit
        ):
            return None
        return sha, branch

    def _git_run_symbolic_head(self, path: Path) -> tuple[str, str] | None:
        from core.execution.worktrees.git import GitCli

        git = GitCli()
        sym = git.run(["symbolic-ref", "HEAD"], git_dir=path, check=False)
        if sym.returncode != 0:
            return None
        branch = sym.stdout.strip().split("/")[-1]
        try:
            sha = self._inspector.resolve_ref(path, sym.stdout.strip())
        except ValueError:
            return None
        return branch, sha

    async def _has_olympus_baseline_marker(
        self,
        session: AsyncSession,
        repo: Repository,
        sha: str,
    ) -> bool:
        if repo.workspace_id is None:
            return False
        workspace = await session.get(RepositoryWorkspace, repo.workspace_id)
        if workspace is None:
            return False
        path = self._locator.resolve(workspace.storage_backend, workspace.logical_location)
        from core.execution.worktrees.git import GitCli

        result = GitCli().run(["show", f"{sha}:OLYMPUS.md"], git_dir=path, check=False)
        if result.returncode != 0:
            return False
        return "governed by Olympus" in result.stdout

    async def _workspace_row(self, session: AsyncSession, repo: Repository) -> RepositoryWorkspace:
        if repo.workspace_id is None:
            raise DomainError(code="WORKSPACE_MISSING", message="No workspace")
        workspace = await session.get(RepositoryWorkspace, repo.workspace_id)
        if workspace is None:
            raise DomainError(code="WORKSPACE_MISSING", message="Workspace row missing")
        workspace.state = WorkspaceState.MATERIALIZING
        await session.flush()
        return workspace

    async def _begin_attempt(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        kind: MaterializationKind,
    ) -> RepositoryMaterialization:
        count = await session.execute(
            select(RepositoryMaterialization).where(
                RepositoryMaterialization.repository_id == repository_id
            )
        )
        attempt_num = len(count.scalars().all()) + 1
        row = RepositoryMaterialization(
            repository_id=repository_id,
            kind=kind,
            attempt=attempt_num,
            status=MaterializationAttemptStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        session.add(row)
        await session.flush()
        return row

    async def _fail_attempt(
        self,
        session: AsyncSession,
        repo: Repository,
        attempt: RepositoryMaterialization,
        exc: Exception,
        ctx: CommandContext,
    ) -> None:
        attempt.status = MaterializationAttemptStatus.FAILED
        attempt.error_class = exc.__class__.__name__
        attempt.error_detail = str(exc)[:2000]
        attempt.finished_at = datetime.now(UTC)
        from_state = repo.status.value
        await self._repos.transitions.transition(
            session,
            "repository",
            repo.id,
            from_state,
            "materialization_failed",
            ctx,
            payload={"reason": str(exc)},
        )
        await session.refresh(repo)
        repo.status_reason = str(exc)[:1024]
        workspace = await session.get(RepositoryWorkspace, repo.workspace_id)
        if workspace:
            logical = workspace.logical_location
            path = self._locator.resolve(workspace.storage_backend, logical)
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
            workspace.state = WorkspaceState.ERROR
