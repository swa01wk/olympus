"""Repository sync — fetch remote default branch, classify drift, adopt EXTERNAL_SYNC."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.findings import FindingService
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import RepositoryStatus, RevisionCause
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.domain.integrations.models import RepositoryEvent
from core.domain.repositories.models import Repository, RepositoryRevision, RepositoryWorkspace
from core.integration.enums import FindingSeverity, FindingSource, ICStatus
from core.integration.models import IntegrationCandidate
from core.integrations.connectors.base import ConnectorAction
from core.integrations.connectors.registry import get_connector_registry
from core.integrations.connectors.secrets import build_credential_resolver
from core.intelligence.code_index.canonical_service import CanonicalIndexService
from core.intelligence.code_index.enums import IndexSource
from core.policy.policy_service import load_policy_file
from core.repositories.git_inspect import GitInspector
from core.repositories.revision import RepositoryRevisionService, RevisionRefs
from core.repositories.workspace_locator import WorkspaceLocator
from core.state.transition_service import TransitionService


class RepositorySyncService:
    def __init__(self) -> None:
        self._locator = WorkspaceLocator()
        self._inspector = GitInspector()
        self._transitions = TransitionService()
        self._revisions = RepositoryRevisionService()

    async def sync(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        ctx: CommandContext,
        *,
        inbound_event_id: uuid.UUID | None = None,
        before_sha: str | None = None,
        after_sha: str | None = None,
        ref: str | None = None,
    ) -> RepositoryEvent | None:
        repo = await session.get(Repository, repository_id)
        if repo is None or repo.workspace_id is None:
            raise DomainError(code="NOT_FOUND", message="Repository not found")
        if repo.status not in {RepositoryStatus.READY, RepositoryStatus.SYNCING}:
            raise DomainError(code="INVALID_STATE", message=f"Cannot sync in {repo.status}")
        ws = await session.get(RepositoryWorkspace, repo.workspace_id)
        if ws is None:
            raise DomainError(code="NOT_FOUND", message="Workspace missing")

        await self._transitions.transition(
            session, "repository", repository_id, repo.status.value, "sync_started", ctx
        )
        await session.refresh(repo)

        cred_resolver = build_credential_resolver(session)
        cred = await cred_resolver.resolve_async(repo.credential_ref)
        connector = f"git_provider_{repo.provider.value.lower()}"
        if repo.provider.value == "LOCAL":
            connector = "git_local"
        registry = get_connector_registry()
        try:
            if connector == "git_local":
                fetch_inputs: dict[str, object] = {
                    "logical_location": ws.logical_location,
                    "remote": "origin",
                }
                if repo.remote_url:
                    fetch_inputs["remote_url"] = repo.remote_url
                fetch = ConnectorAction(
                    connector="git_local",
                    action="fetch",
                    target_resource=str(repo.id),
                    inputs=fetch_inputs,
                    idempotency_key=f"fetch:{repo.id}:{datetime.now(UTC).isoformat()}",
                    correlation_id=ctx.correlation_id,
                    expected_result_schema="FetchResult",
                )
            else:
                fetch = ConnectorAction(
                    connector=connector,
                    action="fetch",
                    target_resource=str(repo.id),
                    inputs={
                        "logical_location": ws.logical_location,
                        "_credential": cred,
                    },
                    idempotency_key=f"fetch:{repo.id}:{datetime.now(UTC).date()}",
                    correlation_id=ctx.correlation_id,
                    expected_result_schema="FetchResult",
                )
            await registry.execute_with_persistence(session, fetch, actor_id=ctx.actor.id)
            git_dir = self._locator.resolve(ws.storage_backend, ws.logical_location)
            remote_ref = f"refs/remotes/origin/{repo.default_branch}"
            remote_head: str | None = None
            head_candidates = [remote_ref]
            if not repo.remote_url:
                head_candidates.append(f"refs/heads/{repo.default_branch}")
            for candidate in head_candidates:
                try:
                    remote_head = self._inspector.resolve_ref(git_dir, candidate)
                    break
                except ValueError:
                    continue
            if remote_head is None and repo.remote_url and repo.remote_url.startswith("file://"):
                from pathlib import Path

                origin_path = Path(repo.remote_url.removeprefix("file://")).resolve()
                try:
                    remote_head = self._inspector.resolve_ref(origin_path, repo.default_branch)
                except ValueError:
                    remote_head = None
            if remote_head is None:
                if after_sha:
                    remote_head = after_sha
                else:
                    raise ValueError(f"Cannot resolve remote head for {repo.default_branch}")
            repo.last_known_head_sha = remote_head
            repo.last_synced_at = datetime.now(UTC)
            canonical = repo.canonical_commit or remote_head
            classification = await self._classify(
                session, repo, git_dir, canonical, remote_head, before_sha, after_sha, ref
            )
            event = RepositoryEvent(
                repository_id=repository_id,
                inbound_event_id=inbound_event_id,
                ref=ref or f"refs/heads/{repo.default_branch}",
                before_sha=before_sha,
                after_sha=remote_head,
                classification=classification,
            )
            session.add(event)
            await session.flush()

            if classification == "STALE":
                event.processed_at = datetime.now(UTC)
                await self._complete_sync(session, repository_id, ctx)
                return event

            if classification in {"NON_DEFAULT_REF", "OLYMPUS_RELEASE"}:
                event.processed_at = datetime.now(UTC)
                await self._complete_sync(session, repository_id, ctx)
                return event

            if classification == "EXTERNAL_REWRITE":
                cycle_row = await session.execute(
                    select(DeliveryCycle)
                    .where(DeliveryCycle.repository_id == repo.id)
                    .order_by(DeliveryCycle.created_at.desc())
                    .limit(1)
                )
                cycle = cycle_row.scalar_one_or_none()
                if cycle is not None:
                    await FindingService().create(
                        session,
                        project_id=repo.project_id,
                        delivery_cycle_id=cycle.id,
                        source=FindingSource.SYSTEM,
                        category="EXTERNAL_REWRITE",
                        severity=FindingSeverity.BLOCKER,
                        title="External force-push detected; acknowledge before adoption",
                        detail={},
                        ctx=ctx,
                    )
                event.processed_at = datetime.now(UTC)
                await self._complete_sync(session, repository_id, ctx)
                return event

            if classification == "EXTERNAL_FAST_FORWARD":
                policy = load_policy_file().get("repository", {}).get("external_sync", {})
                if not policy.get("adopt_fast_forward", True):
                    event.processed_at = datetime.now(UTC)
                    await self._complete_sync(session, repository_id, ctx)
                    return event
                await self._adopt_external(
                    session, repo, ws, event, remote_head, canonical, ctx, force=False
                )
            await self._complete_sync(session, repository_id, ctx)
            return event
        except Exception:
            await self._transitions.transition(
                session,
                "repository",
                repository_id,
                RepositoryStatus.SYNCING.value,
                "sync_failed",
                ctx,
            )
            raise

    async def acknowledge_rewrite(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        ctx: CommandContext,
    ) -> RepositoryRevision:
        repo = await session.get(Repository, repository_id)
        if repo is None or repo.workspace_id is None:
            raise DomainError(code="NOT_FOUND", message="Repository not found")
        head = repo.last_known_head_sha
        if not head:
            raise DomainError(code="NO_REMOTE_HEAD", message="No observed remote head")
        ws = await session.get(RepositoryWorkspace, repo.workspace_id)
        assert ws is not None
        event = RepositoryEvent(
            repository_id=repository_id,
            ref=f"refs/heads/{repo.default_branch}",
            before_sha=repo.canonical_commit,
            after_sha=head,
            classification="EXTERNAL_REWRITE",
        )
        session.add(event)
        await session.flush()
        canonical = repo.canonical_commit or head
        return await self._adopt_external(
            session, repo, ws, event, head, canonical, ctx, force=True
        )

    async def _adopt_external(
        self,
        session: AsyncSession,
        repo: Repository,
        ws: RepositoryWorkspace,
        event: RepositoryEvent,
        remote_head: str,
        canonical: str,
        ctx: CommandContext,
        *,
        force: bool,
    ) -> RepositoryRevision:
        registry = get_connector_registry()
        ff = ConnectorAction(
            connector="git_local",
            action="fast_forward_ref",
            target_resource=str(repo.id),
            inputs={
                "logical_location": ws.logical_location,
                "ref": f"refs/heads/{repo.default_branch}",
                "target_sha": remote_head,
                "force": force,
            },
            idempotency_key=f"external-sync:{event.id}",
            correlation_id=ctx.correlation_id,
            expected_result_schema="FastForwardResult",
        )
        result, _ = await registry.execute_with_persistence(session, ff, actor_id=ctx.actor.id)
        if result.status != "SUCCEEDED":
            raise DomainError(code="SYNC_ADOPT_FAILED", message=result.error_detail or "ff failed")

        await self._supersede_held_ics(session, repo, ctx)
        revision = await self._revisions.advance(
            session,
            repo.id,
            remote_head,
            RevisionCause.EXTERNAL_SYNC,
            RevisionRefs(repository_event_id=event.id),
            canonical,
            ctx,
        )
        from core.intelligence.code_index.canonical import CANONICAL_INDEX_BUILD_CAPABILITY
        from core.intelligence.code_index.enums import IndexKind

        indexer = CanonicalIndexService()
        git_dir = self._locator.resolve(ws.storage_backend, ws.logical_location)
        parent_ver = None
        if canonical and self._inspector.is_ancestor(git_dir, canonical, remote_head):
            parent_ver = await indexer._find_ready_version(  # noqa: SLF001
                session, repo.id, canonical, IndexKind.CANONICAL
            )
        await indexer._indexer.build(  # noqa: SLF001
            session,
            repo.id,
            remote_head,
            IndexKind.CANONICAL,
            IndexSource.EXTERNAL_PUSH,
            ctx,
            scope_ref="",
            parent_index_version_id=parent_ver.id if parent_ver else None,
            _canonical_capability=CANONICAL_INDEX_BUILD_CAPABILITY,
        )
        await self._drift_findings(session, repo, remote_head, ctx)
        event.processed_at = datetime.now(UTC)
        await append_domain_event(
            session,
            aggregate_type="repository",
            aggregate_id=repo.id,
            event_type="repository.synced",
            payload={"sha": remote_head, "classification": event.classification},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=repo.project_id,
        )
        return revision

    async def _supersede_held_ics(
        self, session: AsyncSession, repo: Repository, ctx: CommandContext
    ) -> None:
        ics = await session.execute(
            select(IntegrationCandidate).where(
                IntegrationCandidate.repository_id == repo.id,
                IntegrationCandidate.status.in_(
                    [ICStatus.INTEGRATING, ICStatus.VALIDATING, ICStatus.READY]
                ),
            )
        )
        for ic in ics.scalars():
            if ic.integrated_sha and ic.integrated_sha != repo.canonical_commit:
                ic.status = ICStatus.SUPERSEDED

    async def _drift_findings(
        self,
        session: AsyncSession,
        repo: Repository,
        new_canonical: str,
        ctx: CommandContext,
    ) -> None:
        cycles = await session.execute(
            select(DeliveryCycle).where(
                DeliveryCycle.repository_id == repo.id,
                DeliveryCycle.state.notin_(["COMPLETED", "CANCELLED"]),
            )
        )
        fs = FindingService()
        for cycle in cycles.scalars():
            if cycle.base_sha and cycle.base_sha != new_canonical:
                await fs.create(
                    session,
                    project_id=repo.project_id,
                    delivery_cycle_id=cycle.id,
                    source=FindingSource.SYSTEM,
                    category="EXTERNAL_DRIFT",
                    severity=FindingSeverity.MAJOR,
                    title="Cycle base is no longer canonical after external push",
                    detail={"base_sha": cycle.base_sha, "canonical": new_canonical},
                    ctx=ctx,
                )

    async def _classify(
        self,
        session: AsyncSession,
        repo: Repository,
        git_dir: Path,
        canonical: str,
        remote_head: str,
        before_sha: str | None,
        after_sha: str | None,
        ref: str | None,
    ) -> str:
        path = git_dir
        default_ref = f"refs/heads/{repo.default_branch}"
        if ref and ref != default_ref:
            return "NON_DEFAULT_REF"
        if remote_head == canonical:
            return "OLYMPUS_RELEASE" if repo.released_commit == remote_head else "OLYMPUS_RELEASE"
        if after_sha and before_sha and self._inspector.is_ancestor(path, after_sha, canonical):
            return "STALE"
        if self._inspector.is_ancestor(path, canonical, remote_head):
            return "EXTERNAL_FAST_FORWARD"
        return "EXTERNAL_REWRITE"

    async def _complete_sync(
        self, session: AsyncSession, repository_id: uuid.UUID, ctx: CommandContext
    ) -> None:
        await self._transitions.transition(
            session,
            "repository",
            repository_id,
            RepositoryStatus.SYNCING.value,
            "sync_completed",
            ctx,
        )
