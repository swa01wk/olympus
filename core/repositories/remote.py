"""Remote repository registration validation and attach_remote."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.enums import RepositoryProvider, RepositorySourceType
from core.domain.exceptions import DomainError
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.execution.worktrees.git import GitCli
from core.integrations.connectors.base import ConnectorAction
from core.integrations.connectors.registry import get_connector_registry
from core.integrations.connectors.secrets import build_credential_resolver
from core.release.enums import ReleaseStatus
from core.release.models import Release
from core.repositories.validation import (
    validate_credential_ref,
    validate_provider_supported,
    validate_remote_url,
)
from core.repositories.workspace_locator import WorkspaceLocator


async def release_tag_for_commit(
    session: AsyncSession,
    project_id: uuid.UUID,
    commit_sha: str,
) -> str:
    """Match Stratos tagging: olympus/release/{release.key} at integrated_sha."""
    row = await session.execute(
        select(Release)
        .where(
            Release.project_id == project_id,
            Release.integrated_sha == commit_sha,
            Release.status == ReleaseStatus.RELEASED,
        )
        .order_by(Release.released_at.desc().nulls_last(), Release.created_at.desc())
        .limit(1)
    )
    release = row.scalar_one_or_none()
    if release is None:
        raise DomainError(
            code="NO_RELEASE_TAG",
            message=f"No RELEASED release for commit {commit_sha[:12]}",
        )
    if release.tag:
        return release.tag
    return f"olympus/release/{release.key}"


class RemoteRepositoryService:
    async def validate_registration(
        self,
        session: AsyncSession,
        provider: RepositoryProvider,
        remote_url: str,
        credential_ref: str,
    ) -> None:
        validate_provider_supported(provider)
        validate_credential_ref(credential_ref)
        validate_remote_url(remote_url)
        if provider in {RepositoryProvider.GITLAB, RepositoryProvider.BITBUCKET}:
            raise DomainError(code="PROVIDER_NOT_SUPPORTED", message=f"{provider} not supported")
        if provider == RepositoryProvider.LOCAL:
            if not remote_url.startswith("file://"):
                raise DomainError(code="INVALID_REMOTE_URL", message="LOCAL requires file://")
            return
        if not remote_url.startswith("https://") and not remote_url.startswith(
            ("http://127.0.0.1", "http://localhost")
        ):
            raise DomainError(code="INVALID_REMOTE_URL", message="Remote requires HTTPS")
        cred = build_credential_resolver(session)
        status = cred.status(credential_ref)
        if status in {"MISSING", "INVALID"}:
            raise DomainError(code="CREDENTIAL_MISSING", message=f"credential {status}")
        connector = f"git_provider_{provider.value.lower()}"
        registry = get_connector_registry()
        resolved = await cred.resolve_async(credential_ref)
        action = ConnectorAction(
            connector=connector,
            action="validate_registration",
            target_resource=remote_url,
            inputs={"remote_url": remote_url, "_credential": resolved},
            idempotency_key=f"validate:{remote_url}",
            correlation_id=str(uuid.uuid4()),
            expected_result_schema="ValidateResult",
        )
        result, _ = await registry.execute_with_persistence(session, action)
        if result.status != "SUCCEEDED":
            raise DomainError(
                code="VALIDATION_FAILED",
                message=result.error_detail or "Provider validation failed",
            )

    async def attach_remote(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        provider: RepositoryProvider,
        remote_url: str,
        credential_ref: str,
        ctx: CommandContext,
    ) -> Repository:
        repo = await session.get(Repository, repository_id)
        if repo is None:
            raise DomainError(code="NOT_FOUND", message="Repository not found")
        remote = repo.remote_url or ""
        local_external_publish = (
            repo.source_type == RepositorySourceType.EXTERNAL_CLONE
            and repo.provider == RepositoryProvider.LOCAL
            and remote.startswith("file://")
        )
        if (
            repo.source_type != RepositorySourceType.GREENFIELD_MANAGED
            and not local_external_publish
        ):
            raise DomainError(
                code="INVALID_SOURCE_TYPE",
                message="attach_remote requires GREENFIELD_MANAGED or LOCAL EXTERNAL_CLONE",
            )
        await self.validate_registration(session, provider, remote_url, credential_ref)
        if repo.released_commit is None:
            raise DomainError(code="NO_RELEASE", message="Release required before attach_remote")
        ws = (
            await session.get(RepositoryWorkspace, repo.workspace_id) if repo.workspace_id else None
        )
        if ws is None:
            raise DomainError(code="NO_WORKSPACE", message="Workspace missing")
        cred = await build_credential_resolver(session).resolve_async(credential_ref)
        connector = f"git_provider_{provider.value.lower()}"
        registry = get_connector_registry()
        tag = await release_tag_for_commit(session, repo.project_id, repo.released_commit)
        push = ConnectorAction(
            connector=connector,
            action="push_release",
            target_resource=str(repo.id),
            inputs={
                "logical_location": ws.logical_location,
                "branch": repo.default_branch,
                "sha": repo.released_commit,
                "tag": tag,
                "remote_url": remote_url,
                "_credential": cred,
            },
            idempotency_key=f"attach-remote:{repo.id}",
            correlation_id=ctx.correlation_id,
            expected_result_schema="PushReleaseResult",
            policy_context={"release_executor": True},
        )
        result, _ = await registry.execute_with_persistence(session, push, actor_id=ctx.actor.id)
        if result.status != "SUCCEEDED":
            raise DomainError(code="PUSH_FAILED", message=result.error_detail or "push failed")
        token = cred.secret.get_secret_value() if cred else None
        git = GitCli(credential_env={"OLYMPUS_GIT_CREDENTIAL": token} if token else None)
        bare = WorkspaceLocator().resolve("LOCAL_FILESYSTEM", ws.logical_location)
        set_url = git.run(["remote", "set-url", "origin", remote_url], git_dir=bare, check=False)
        if set_url.returncode != 0:
            git.run(["remote", "add", "origin", remote_url], git_dir=bare, check=False)
        repo.provider = provider
        repo.remote_url = remote_url
        repo.credential_ref = credential_ref
        webhook = ConnectorAction(
            connector=connector,
            action="ensure_webhook",
            target_resource=str(repo.id),
            inputs={"remote_url": remote_url, "_credential": cred},
            idempotency_key=f"webhook:{repo.id}",
            correlation_id=ctx.correlation_id,
            expected_result_schema="WebhookResult",
        )
        await registry.execute_with_persistence(session, webhook, actor_id=ctx.actor.id)
        return repo
