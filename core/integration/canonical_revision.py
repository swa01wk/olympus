"""Canonical revision lock and revert on cycle abandonment."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import RevisionCause
from core.domain.events.append import append_domain_event
from core.domain.repositories.models import Repository, RepositoryRevision
from core.integration.enums import ICStatus
from core.integration.models import IntegrationCandidate
from core.intelligence.code_index.enums import IndexKind, IndexVersionStatus
from core.intelligence.code_index.models import CodeIndexVersion
from core.repositories.revision import RepositoryRevisionService
from core.traceability.models import RepositoryIndexPointer


class CanonicalRevisionGuardian:
    async def holds_unreleased_revision(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        *,
        exclude_cycle_id: uuid.UUID | None = None,
    ) -> IntegrationCandidate | None:
        rev = await session.execute(
            select(RepositoryRevision)
            .where(
                RepositoryRevision.repository_id == repository_id,
                RepositoryRevision.cause == RevisionCause.INTEGRATION_READY,
            )
            .order_by(RepositoryRevision.sequence.desc())
            .limit(1)
        )
        latest = rev.scalar_one_or_none()
        if latest is None or latest.integration_candidate_id is None:
            return None
        ic = await session.get(IntegrationCandidate, latest.integration_candidate_id)
        if ic is None or ic.status != ICStatus.READY:
            return None
        if exclude_cycle_id is not None and ic.delivery_cycle_id == exclude_cycle_id:
            return None
        repo = await session.get(Repository, repository_id)
        if repo is None or repo.released_commit == repo.canonical_commit:
            return None
        return ic

    async def on_cycle_terminal(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> RepositoryRevision | None:
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None or cycle.repository_id is None:
            return None
        ic = await self.holds_unreleased_revision(
            session, cycle.repository_id, exclude_cycle_id=None
        )
        if ic is None or ic.delivery_cycle_id != cycle_id:
            return None
        return await self._revert_held(session, cycle.repository_id, ic, ctx)

    async def _revert_held(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        ic: IntegrationCandidate,
        ctx: CommandContext,
    ) -> RepositoryRevision:
        repo = await session.get(Repository, repository_id)
        if repo is None:
            raise ValueError("repository missing")
        revert_target = await self._default_branch_head_revision(session, repository_id)
        to_sha = revert_target.commit_sha if revert_target else repo.registered_sha or ic.base_sha
        reverts_id = (
            await session.execute(
                select(RepositoryRevision)
                .where(
                    RepositoryRevision.repository_id == repository_id,
                    RepositoryRevision.cause == RevisionCause.INTEGRATION_READY,
                    RepositoryRevision.integration_candidate_id == ic.id,
                )
                .limit(1)
            )
        ).scalar_one()
        revision = await RepositoryRevisionService().revert(
            session,
            repository_id,
            to_sha,
            reverts_revision_id=reverts_id.id,
            _reason="cycle_abandoned",
            ctx=ctx,
        )
        pointer = await session.get(RepositoryIndexPointer, repository_id)
        if pointer is None:
            pointer = RepositoryIndexPointer(repository_id=repository_id)
            session.add(pointer)
        idx = await session.execute(
            select(CodeIndexVersion)
            .where(
                CodeIndexVersion.repository_id == repository_id,
                CodeIndexVersion.commit_sha == to_sha,
                CodeIndexVersion.kind == IndexKind.CANONICAL,
                CodeIndexVersion.status == IndexVersionStatus.READY,
            )
            .order_by(CodeIndexVersion.created_at.desc())
            .limit(1)
        )
        canonical = idx.scalar_one_or_none()
        pointer.canonical_index_version_id = canonical.id if canonical else None
        ic.status = ICStatus.SUPERSEDED
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="repository",
            aggregate_id=repository_id,
            event_type="repository.canonical_reverted",
            payload={"to_sha": to_sha, "integration_candidate_id": str(ic.id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=repo.project_id,
        )
        from core.intelligence.impact.staleness import StalenessService

        await StalenessService().on_canonical_revision_changed(
            session,
            repository_id,
            repo.canonical_commit,
            to_sha,
            "repository.canonical_reverted",
            exclude_cycle_id=ic.delivery_cycle_id,
            ctx=ctx,
        )
        return revision

    async def _default_branch_head_revision(
        self, session: AsyncSession, repository_id: uuid.UUID
    ) -> RepositoryRevision | None:
        causes = (
            RevisionCause.MATERIALIZED,
            RevisionCause.RELEASED,
            RevisionCause.EXTERNAL_SYNC,
        )
        result = await session.execute(
            select(RepositoryRevision)
            .where(
                RepositoryRevision.repository_id == repository_id,
                RepositoryRevision.cause.in_(causes),
            )
            .order_by(RepositoryRevision.sequence.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
