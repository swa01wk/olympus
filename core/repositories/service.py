"""Repository metadata registration, validation, and materialization recording (no Git in prod)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.enums import (
    RepositoryProvider,
    RepositorySourceType,
    RepositoryStatus,
    RevisionCause,
    WorkspaceState,
)
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.repositories.revision import RepositoryRevisionService, RevisionRefs
from core.repositories.validation import (
    validate_credential_ref,
    validate_provider_supported,
    validate_remote_url,
)
from core.repositories.workspace_locator import WorkspaceLocator
from core.state.transition_service import TransitionService


@dataclass
class RepositoryWorkspaceView:
    id: uuid.UUID
    workspace_type: str
    storage_backend: str
    logical_location: str
    materialized_commit: str | None
    state: WorkspaceState


@dataclass
class RepositoryView:
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    source_type: RepositorySourceType
    provider: RepositoryProvider
    remote_url: str | None
    default_branch: str
    registered_sha: str | None
    canonical_commit: str | None
    released_commit: str | None
    status: RepositoryStatus
    status_reason: str | None
    credential_ref: str
    credential_status: str
    workspace: RepositoryWorkspaceView | None


class RepositoryService:
    def __init__(
        self,
        locator: WorkspaceLocator | None = None,
        transitions: TransitionService | None = None,
        revisions: RepositoryRevisionService | None = None,
    ) -> None:
        self.locator = locator or WorkspaceLocator()
        self.transitions = transitions or TransitionService()
        self.revisions = revisions or RepositoryRevisionService()

    async def register_external(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        name: str,
        provider: RepositoryProvider,
        remote_url: str,
        default_branch: str,
        credential_ref: str,
        ctx: CommandContext,
    ) -> Repository:
        validate_provider_supported(provider)
        validate_credential_ref(credential_ref)
        validate_remote_url(remote_url)
        if provider == RepositoryProvider.LOCAL:
            if not remote_url.startswith("file://"):
                raise DomainError(
                    code="INVALID_REMOTE_URL",
                    message="LOCAL external repositories require file:// remote_url",
                )
        elif provider in {RepositoryProvider.GITHUB, RepositoryProvider.GITEA}:
            if not remote_url.startswith("https://"):
                raise DomainError(
                    code="INVALID_REMOTE_URL",
                    message="Remote providers require HTTPS remote_url",
                )
        else:
            raise DomainError(
                code="PROVIDER_NOT_SUPPORTED",
                message=f"Provider {provider} is not supported",
            )
        existing = await session.execute(
            select(Repository).where(Repository.project_id == project_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise DomainError(
                code="REPOSITORY_ALREADY_EXISTS",
                message="Project already has a repository",
            )
        repo = Repository(
            project_id=project_id,
            name=name,
            source_type=RepositorySourceType.EXTERNAL_CLONE,
            provider=provider,
            remote_url=remote_url,
            default_branch=default_branch or "main",
            status=RepositoryStatus.CLONING,
            credential_ref=credential_ref,
        )
        session.add(repo)
        await session.flush()
        logical = self.locator.canonical_location(project_id)
        workspace = RepositoryWorkspace(
            repository_id=repo.id,
            logical_location=logical,
            state=WorkspaceState.PENDING,
        )
        session.add(workspace)
        await session.flush()
        repo.workspace_id = workspace.id
        await append_domain_event(
            session,
            aggregate_type="repository",
            aggregate_id=repo.id,
            event_type="repository.registered",
            payload={"source_type": repo.source_type.value, "provider": provider.value},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=project_id,
        )
        return repo

    async def declare_managed(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        ctx: CommandContext,
    ) -> Repository:
        existing = await session.execute(
            select(Repository).where(Repository.project_id == project_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise DomainError(
                code="REPOSITORY_ALREADY_EXISTS",
                message="Project already has a repository",
            )
        repo = Repository(
            project_id=project_id,
            name="managed",
            source_type=RepositorySourceType.GREENFIELD_MANAGED,
            provider=RepositoryProvider.LOCAL,
            remote_url=None,
            status=RepositoryStatus.PROVISIONING,
            credential_ref="none:",
        )
        session.add(repo)
        await session.flush()
        workspace = RepositoryWorkspace(
            repository_id=repo.id,
            logical_location=self.locator.canonical_location(project_id),
            state=WorkspaceState.PENDING,
        )
        session.add(workspace)
        await session.flush()
        repo.workspace_id = workspace.id
        await append_domain_event(
            session,
            aggregate_type="repository",
            aggregate_id=repo.id,
            event_type="repository.declared",
            payload={"source_type": repo.source_type.value},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=project_id,
        )
        return repo

    async def record_materialization(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        sha: str,
        default_branch: str,
        ctx: CommandContext,
    ) -> Repository:
        repo = await session.get(Repository, repository_id)
        if repo is None:
            raise DomainError(code="NOT_FOUND", message="Repository not found")
        if repo.registered_sha is not None:
            raise DomainError(
                code="ALREADY_MATERIALIZED", message="Repository already materialized"
            )
        workspace = (
            await session.get(RepositoryWorkspace, repo.workspace_id) if repo.workspace_id else None
        )
        if workspace is None:
            raise DomainError(code="WORKSPACE_MISSING", message="Canonical workspace missing")
        repo.registered_sha = sha
        repo.default_branch = default_branch
        await self.revisions.advance(
            session,
            repository_id,
            sha,
            RevisionCause.MATERIALIZED,
            RevisionRefs(),
            expected_current=None,
            ctx=ctx,
        )
        await self.transitions.transition(
            session,
            "repository",
            repository_id,
            repo.status.value,
            "record_materialization",
            ctx,
        )
        workspace.state = WorkspaceState.READY
        workspace.materialized_commit = sha
        return repo

    async def get_view(self, session: AsyncSession, repository_id: uuid.UUID) -> RepositoryView:
        repo = await session.get(Repository, repository_id)
        if repo is None:
            raise DomainError(code="NOT_FOUND", message="Repository not found")
        workspace_view = None
        if repo.workspace_id:
            ws = await session.get(RepositoryWorkspace, repo.workspace_id)
            if ws:
                workspace_view = RepositoryWorkspaceView(
                    id=ws.id,
                    workspace_type=ws.workspace_type,
                    storage_backend=ws.storage_backend,
                    logical_location=ws.logical_location,
                    materialized_commit=ws.materialized_commit,
                    state=ws.state,
                )
        return RepositoryView(
            id=repo.id,
            project_id=repo.project_id,
            name=repo.name,
            source_type=repo.source_type,
            provider=repo.provider,
            remote_url=repo.remote_url,
            default_branch=repo.default_branch,
            registered_sha=repo.registered_sha,
            canonical_commit=repo.canonical_commit,
            released_commit=repo.released_commit,
            status=repo.status,
            status_reason=repo.status_reason,
            credential_ref=repo.credential_ref,
            credential_status="REFERENCE_ONLY",
            workspace=workspace_view,
        )
