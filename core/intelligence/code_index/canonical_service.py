"""Canonical index promotion and candidate index builds."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.candidate_commits.models import CandidateCommit
from core.domain.enums import RevisionCause
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError, StateConflict
from core.domain.repositories.models import Repository
from core.integration.enums import ICStatus
from core.integration.models import IntegrationCandidate, IntegrationCandidateCommit
from core.intelligence.code_index.canonical import CANONICAL_INDEX_BUILD_CAPABILITY
from core.intelligence.code_index.changes import compute_entity_changes
from core.intelligence.code_index.enums import IndexKind, IndexSource, IndexVersionStatus
from core.intelligence.code_index.indexer import CodeIndexer
from core.intelligence.code_index.models import CodeIndexVersion
from core.policy.policy_service import get_cached_policy_content
from core.repositories.revision import RepositoryRevisionService, RevisionRefs
from core.traceability.models import RepositoryIndexPointer
from core.traceability.spec_code_links.service import SpecCodeLinkService


class CanonicalIndexService:
    def __init__(self, *, indexer: CodeIndexer | None = None) -> None:
        self._indexer = indexer or CodeIndexer()

    async def build_candidate(
        self,
        session: AsyncSession,
        execution_id: uuid.UUID,
        ctx: CommandContext,
    ) -> CodeIndexVersion:
        from core.domain.candidate_commits.models import CandidateCommit
        from core.domain.executions.models import Execution

        execution = await session.get(Execution, execution_id)
        if execution is None:
            raise DomainError(code="NOT_FOUND", message="Execution not found")
        cc = await session.execute(
            select(CandidateCommit).where(CandidateCommit.execution_id == execution_id)
        )
        commit = cc.scalar_one_or_none()
        if commit is None:
            raise DomainError(code="NO_CANDIDATE_COMMIT", message="No candidate commit")
        parent: CodeIndexVersion | None = None
        if commit.base_sha:
            parent = await self._find_ready_version(
                session, commit.repository_id, commit.base_sha, IndexKind.CANONICAL
            ) or await self._find_ready_version(
                session, commit.repository_id, commit.base_sha, IndexKind.CANDIDATE
            )
        return await self._indexer.build(
            session,
            commit.repository_id,
            commit.sha,
            IndexKind.CANDIDATE,
            IndexSource.EXECUTION,
            ctx,
            scope_ref=execution.key,
            parent_index_version_id=parent.id if parent else None,
            _canonical_capability=None,
        )

    async def promote_ic(
        self,
        session: AsyncSession,
        ic_id: uuid.UUID,
        ctx: CommandContext,
    ) -> CodeIndexVersion:
        ic = await session.get(IntegrationCandidate, ic_id)
        if ic is None:
            raise DomainError(code="NOT_FOUND", message="IC not found")
        if ic.status != ICStatus.VALIDATING or ic.integrated_sha is None:
            raise DomainError(code="IC_NOT_VALIDATING", message="IC not in VALIDATING")
        repo = await session.get(Repository, ic.repository_id)
        if repo is None:
            raise DomainError(code="NOT_FOUND", message="Repository not found")

        policy = get_cached_policy_content()
        advance_on = policy.get("repository", {}).get("canonical_advance_on", "INTEGRATION_READY")
        if advance_on != "INTEGRATION_READY":
            raise DomainError(code="POLICY_BLOCKED", message="Canonical advance policy blocked")

        parent_canonical = await self._find_ready_version(
            session, ic.repository_id, ic.base_sha or "", IndexKind.CANONICAL
        )
        use_incremental = False
        if parent_canonical and ic.base_sha and ic.integrated_sha:
            from pathlib import Path

            from core.domain.repositories.models import RepositoryWorkspace
            from core.repositories.git_inspect import GitInspector
            from core.repositories.workspace_locator import WorkspaceLocator

            ws = await session.get(RepositoryWorkspace, repo.workspace_id)
            if ws:
                git_dir = WorkspaceLocator().resolve(ws.storage_backend, ws.logical_location)
                use_incremental = GitInspector().is_ancestor(
                    Path(git_dir), ic.base_sha, ic.integrated_sha
                )
        if use_incremental and parent_canonical:
            from core.intelligence.code_index.incremental import IncrementalIndexBuilder

            version = await IncrementalIndexBuilder(
                locator=self._indexer._locator
            ).build_incremental(
                session,
                ic.repository_id,
                parent_canonical.id,
                ic.integrated_sha,
                IndexKind.CANONICAL,
                IndexSource.INTEGRATION_CANDIDATE,
                ctx,
                scope_ref=ic.key,
                _canonical_capability=CANONICAL_INDEX_BUILD_CAPABILITY,
            )
        else:
            version = await self._indexer.build(
                session,
                ic.repository_id,
                ic.integrated_sha,
                IndexKind.CANONICAL,
                IndexSource.INTEGRATION_CANDIDATE,
                ctx,
                scope_ref=ic.key,
                _canonical_capability=CANONICAL_INDEX_BUILD_CAPABILITY,
            )

        await self._record_entity_changes_for_ic(session, ic, version.id)

        links = await SpecCodeLinkService().materialize_generated(session, ic.id, version.id, ctx)

        from core.traceability.spec_code_links.refresh import SpecCodeLinkRefreshService

        await SpecCodeLinkRefreshService().refresh(
            session,
            repository_id=ic.repository_id,
            canonical_index_version_id=version.id,
            delivery_cycle_id=ic.delivery_cycle_id,
            project_id=repo.project_id,
            ctx=ctx,
        )

        pointer = await session.get(RepositoryIndexPointer, ic.repository_id)
        if pointer is None:
            pointer = RepositoryIndexPointer(repository_id=ic.repository_id)
            session.add(pointer)
        prev_canonical_id = pointer.canonical_index_version_id
        pointer.canonical_index_version_id = version.id
        await session.flush()

        if prev_canonical_id and prev_canonical_id != version.id:
            prev = await session.get(CodeIndexVersion, prev_canonical_id)
            if prev and prev.source == IndexSource.INTEGRATION_CANDIDATE:
                prev.status = IndexVersionStatus.SUPERSEDED

        try:
            revision = await RepositoryRevisionService().advance(
                session,
                ic.repository_id,
                ic.integrated_sha,
                RevisionCause.INTEGRATION_READY,
                RevisionRefs(
                    integration_candidate_id=ic.id,
                    canonical_index_version_id=version.id,
                    delivery_cycle_id=ic.delivery_cycle_id,
                ),
                expected_current=ic.base_sha,
                ctx=ctx,
            )
        except StateConflict as exc:
            ic.status = ICStatus.SUPERSEDED
            await session.flush()
            from core.assurance.findings import FindingService
            from core.domain.delivery_cycles.models import DeliveryCycle
            from core.integration.enums import FindingSeverity, FindingSource

            cycle = await session.get(DeliveryCycle, ic.delivery_cycle_id)
            if cycle:
                await FindingService().create(
                    session,
                    project_id=cycle.project_id,
                    delivery_cycle_id=cycle.id,
                    source=FindingSource.INTEGRATION,
                    category="CANONICAL_MOVED_DURING_INTEGRATION",
                    severity=FindingSeverity.MAJOR,
                    title="Canonical revision moved during integration validation",
                    detail={
                        "expected": (exc.details or {}).get("expected"),
                        "current": (exc.details or {}).get("current"),
                    },
                    ctx=ctx,
                    integration_candidate_id=ic.id,
                )
            raise

        ic.canonical_index_version_id = version.id
        ic.canonical_revision_id = revision.id
        ic.status = ICStatus.READY
        await session.flush()

        await self._discard_candidate_indexes(session, ic.id)

        await append_domain_event(
            session,
            aggregate_type="code_index_version",
            aggregate_id=version.id,
            event_type="code_index.updated",
            payload={"repository_id": str(ic.repository_id), "commit_sha": ic.integrated_sha},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=repo.project_id,
            delivery_cycle_id=ic.delivery_cycle_id,
        )
        await append_domain_event(
            session,
            aggregate_type="integration_candidate",
            aggregate_id=ic.id,
            event_type="integration.ready",
            payload={
                "integrated_sha": ic.integrated_sha,
                "canonical_index_version_id": str(version.id),
                "links_created": len(links),
            },
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=repo.project_id,
            delivery_cycle_id=ic.delivery_cycle_id,
        )
        from core.assurance.orchestrator import AssuranceOrchestrator
        from core.intelligence.impact.staleness import StalenessService

        await StalenessService().on_code_index_updated(
            session,
            ic.repository_id,
            ic.integrated_sha,
            exclude_cycle_id=ic.delivery_cycle_id,
            ctx=ctx,
        )
        await AssuranceOrchestrator().on_integration_ready(session, ic.id, ctx)
        return version

    async def _record_entity_changes_for_ic(
        self,
        session: AsyncSession,
        ic: IntegrationCandidate,
        canonical_version_id: uuid.UUID,
    ) -> None:
        links = await session.execute(
            select(IntegrationCandidateCommit).where(
                IntegrationCandidateCommit.integration_candidate_id == ic.id,
                IntegrationCandidateCommit.included.is_(True),
            )
        )
        for link in links.scalars():
            cc = await session.get(CandidateCommit, link.candidate_commit_id)
            if cc is None:
                continue
            cand = await self._find_ready_version(
                session, ic.repository_id, cc.sha, IndexKind.CANDIDATE, scope_ref=None
            )
            base = await self._find_ready_version(
                session, ic.repository_id, cc.base_sha, IndexKind.CANONICAL
            ) or await self._find_ready_version(
                session, ic.repository_id, cc.base_sha, IndexKind.CANDIDATE
            )
            if cand is None or base is None or ic.integrated_sha is None:
                continue
            await compute_entity_changes(
                session,
                repository_id=ic.repository_id,
                base_version_id=base.id,
                candidate_version_id=cand.id,
                execution_id=cc.execution_id,
                task_id=cc.task_id,
                candidate_commit_sha=cc.sha,
                integration_candidate_id=ic.id,
                integrated_sha=ic.integrated_sha,
            )

    async def _discard_candidate_indexes(self, session: AsyncSession, ic_id: uuid.UUID) -> None:
        ic = await session.get(IntegrationCandidate, ic_id)
        if ic is None:
            return
        links = await session.execute(
            select(IntegrationCandidateCommit).where(
                IntegrationCandidateCommit.integration_candidate_id == ic.id
            )
        )
        for link in links.scalars():
            cc = await session.get(CandidateCommit, link.candidate_commit_id)
            if cc is None:
                continue
            from core.domain.executions.models import Execution

            ex = await session.get(Execution, cc.execution_id)
            scope = ex.key if ex else ""
            result = await session.execute(
                select(CodeIndexVersion).where(
                    CodeIndexVersion.repository_id == ic.repository_id,
                    CodeIndexVersion.commit_sha == cc.sha,
                    CodeIndexVersion.kind == IndexKind.CANDIDATE,
                    CodeIndexVersion.scope_ref == scope,
                    CodeIndexVersion.status == IndexVersionStatus.READY,
                )
            )
            for ver in result.scalars():
                ver.status = IndexVersionStatus.DISCARDED

    async def _find_ready_version(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        sha: str,
        kind: IndexKind,
        scope_ref: str | None = "",
    ) -> CodeIndexVersion | None:
        q = select(CodeIndexVersion).where(
            CodeIndexVersion.repository_id == repository_id,
            CodeIndexVersion.commit_sha == sha,
            CodeIndexVersion.kind == kind,
            CodeIndexVersion.status == IndexVersionStatus.READY,
        )
        if scope_ref is not None:
            q = q.where(CodeIndexVersion.scope_ref == scope_ref)
        result = await session.execute(q.order_by(CodeIndexVersion.created_at.desc()).limit(1))
        return result.scalar_one_or_none()

    async def promote_repository_snapshot(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        sha: str,
        ctx: CommandContext,
    ) -> CodeIndexVersion:
        repo = await session.get(Repository, repository_id)
        if repo is None or repo.canonical_commit != sha:
            raise DomainError(
                code="CANONICAL_SHA_MISMATCH",
                message="sha must equal repository.canonical_commit",
            )
        return await self._indexer.build(
            session,
            repository_id,
            sha,
            IndexKind.CANONICAL,
            IndexSource.REPOSITORY_SNAPSHOT,
            ctx,
            scope_ref="",
            _canonical_capability=CANONICAL_INDEX_BUILD_CAPABILITY,
        )
