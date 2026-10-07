"""Scheduler loop: materialize repositories in PROVISIONING/CLONING."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.enums import RepositorySourceType, RepositoryStatus
from core.domain.repositories.models import Repository
from core.repositories.materialization import RepositoryMaterializationService
from core.repositories.service import RepositoryService


class MaterializationLoop:
    def __init__(self, service: RepositoryMaterializationService | None = None) -> None:
        self._service = service or RepositoryMaterializationService()
        self._repos = RepositoryService()

    async def run_once(self, session: AsyncSession, ctx: CommandContext) -> int:
        processed = 0
        result = await session.execute(
            select(Repository).where(
                Repository.status.in_([RepositoryStatus.PROVISIONING, RepositoryStatus.CLONING])
            )
        )
        for repo in result.scalars():
            if repo.registered_sha is not None:
                continue
            adopted = await self._service.resolve_materialization_head(session, repo.id)
            if adopted is not None:
                head, branch = adopted
                await self._repos.record_materialization(session, repo.id, head, branch, ctx)
                processed += 1
                continue
            if repo.source_type == RepositorySourceType.GREENFIELD_MANAGED:
                await self._service.provision_managed(session, repo.id, ctx)
            else:
                await self._service.materialize_external(session, repo.id, ctx)
            processed += 1
        return processed
