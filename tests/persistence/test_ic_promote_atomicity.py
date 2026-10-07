from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from core.domain.enums import RevisionCause
from core.domain.exceptions import DomainError
from core.integration.enums import ICStatus
from core.integration.models import IntegrationCandidate
from core.intelligence.code_index.canonical_service import CanonicalIndexService
from core.intelligence.code_index.enums import IndexVersionStatus
from core.intelligence.code_index.models import CodeIndexVersion
from core.repositories.revision import RepositoryRevisionService, RevisionRefs
from core.repositories.service import RepositoryService

pytestmark = pytest.mark.persistence


async def _stub_index_build(session, repository_id, sha, kind, source, ctx, **kwargs):
    version = CodeIndexVersion(
        repository_id=repository_id,
        commit_sha=sha,
        kind=kind,
        source=source,
        scope_ref=kwargs.get("scope_ref", ""),
        status=IndexVersionStatus.READY,
        indexer_version="test-stub",
        stats={},
    )
    session.add(version)
    await session.flush()
    return version


@pytest.mark.asyncio
async def test_promote_supersedes_ic_when_canonical_moved(
    db_session,
    sample_project,
    system_ctx,
) -> None:
    from core.domain.delivery_cycles.models import DeliveryCycle
    from core.domain.enums import DeliveryCycleType

    repo = await RepositoryService().declare_managed(db_session, sample_project.id, system_ctx)
    base = "a" * 40
    await RepositoryService().record_materialization(db_session, repo.id, base, "main", system_ctx)
    cycle = DeliveryCycle(
        project_id=sample_project.id,
        key="C-promote",
        type=DeliveryCycleType.FEATURE_CHANGE,
        objective="promote",
        state="DEVELOPMENT",
        state_version=0,
        opened_by_actor_id=system_ctx.actor.id,
        repository_id=repo.id,
        base_sha=base,
    )
    db_session.add(cycle)
    await db_session.flush()
    ic = IntegrationCandidate(
        key="IC-PROM",
        delivery_cycle_id=cycle.id,
        repository_id=repo.id,
        base_sha=base,
        integration_branch="olympus/integration/IC-PROM",
        status=ICStatus.VALIDATING,
        ordering=[],
        integrated_sha="b" * 40,
    )
    db_session.add(ic)
    await db_session.flush()

    external = "c" * 40
    await RepositoryRevisionService().advance(
        db_session,
        repo.id,
        external,
        RevisionCause.EXTERNAL_SYNC,
        RevisionRefs(),
        expected_current=base,
        ctx=system_ctx,
    )

    svc = CanonicalIndexService()
    svc._indexer.build = AsyncMock(side_effect=_stub_index_build)
    with pytest.raises(DomainError):
        await svc.promote_ic(db_session, ic.id, system_ctx)
    await db_session.refresh(ic)
    assert ic.status == ICStatus.SUPERSEDED
