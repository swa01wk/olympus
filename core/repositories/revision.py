"""Single writer for canonical_commit, released_commit, and append-only repository_revisions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.enums import RepositoryStatus, RevisionCause
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError, StateConflict
from core.domain.repositories.models import Repository, RepositoryRevision


@dataclass
class RevisionRefs:
    integration_candidate_id: uuid.UUID | None = None
    release_id: uuid.UUID | None = None
    repository_event_id: uuid.UUID | None = None
    canonical_index_version_id: uuid.UUID | None = None
    delivery_cycle_id: uuid.UUID | None = None
    reverts_revision_id: uuid.UUID | None = None


class RepositoryRevisionService:
    """Single writer for canonical_commit, released_commit, and revision history."""

    async def advance(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        to_sha: str,
        cause: RevisionCause,
        refs: RevisionRefs,
        expected_current: str | None,
        ctx: CommandContext,
    ) -> RepositoryRevision:
        result = await session.execute(
            select(Repository).where(Repository.id == repository_id).with_for_update()
        )
        repo = result.scalar_one()
        if expected_current is not None and repo.canonical_commit != expected_current:
            raise StateConflict(
                current=repo.canonical_commit or "",
                expected=expected_current,
            )
        if cause != RevisionCause.MATERIALIZED and repo.status not in {
            RepositoryStatus.READY,
            RepositoryStatus.SYNCING,
        }:
            raise DomainError(
                code="REPOSITORY_NOT_READY",
                message=f"Repository status {repo.status} cannot advance canonical commit",
            )
        seq_result = await session.execute(
            select(func.coalesce(func.max(RepositoryRevision.sequence), 0)).where(
                RepositoryRevision.repository_id == repository_id
            )
        )
        next_seq = int(seq_result.scalar_one()) + 1
        from_sha = repo.canonical_commit
        revision = RepositoryRevision(
            repository_id=repository_id,
            sequence=next_seq,
            commit_sha=to_sha,
            cause=cause,
            integration_candidate_id=refs.integration_candidate_id,
            release_id=refs.release_id,
            repository_event_id=refs.repository_event_id,
            canonical_index_version_id=refs.canonical_index_version_id,
            delivery_cycle_id=refs.delivery_cycle_id,
            reverts_revision_id=refs.reverts_revision_id,
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
        )
        session.add(revision)
        await session.flush()
        repo.canonical_commit = to_sha
        repo.state_version += 1
        await append_domain_event(
            session,
            aggregate_type="repository",
            aggregate_id=repository_id,
            event_type="repository.canonical_advanced",
            payload={
                "from_sha": from_sha,
                "to_sha": to_sha,
                "cause": cause.value,
                "sequence": next_seq,
            },
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=repo.project_id,
        )
        from core.intelligence.impact.staleness import StalenessService

        await StalenessService().on_canonical_revision_changed(
            session,
            repository_id,
            from_sha,
            to_sha,
            cause.value,
            exclude_cycle_id=refs.delivery_cycle_id,
            ctx=ctx,
        )
        return revision

    async def mark_released(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        sha: str,
        release_id: uuid.UUID,
        ctx: CommandContext,
    ) -> RepositoryRevision:
        result = await session.execute(
            select(Repository).where(Repository.id == repository_id).with_for_update()
        )
        repo = result.scalar_one()
        if repo.canonical_commit != sha:
            raise DomainError(
                code="RELEASE_SHA_MISMATCH",
                message="released commit must equal canonical_commit",
            )
        refs = RevisionRefs(release_id=release_id)
        revision = await self.advance(
            session,
            repository_id,
            sha,
            RevisionCause.RELEASED,
            refs,
            expected_current=sha,
            ctx=ctx,
        )
        repo.released_commit = sha
        return revision

    async def revert(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        to_sha: str,
        reverts_revision_id: uuid.UUID,
        _reason: str,
        ctx: CommandContext,
    ) -> RepositoryRevision:
        result = await session.execute(
            select(Repository).where(Repository.id == repository_id).with_for_update()
        )
        repo = result.scalar_one()
        refs = RevisionRefs(reverts_revision_id=reverts_revision_id)
        return await self.advance(
            session,
            repository_id,
            to_sha,
            RevisionCause.REVERTED,
            refs,
            expected_current=repo.canonical_commit,
            ctx=ctx,
        )
