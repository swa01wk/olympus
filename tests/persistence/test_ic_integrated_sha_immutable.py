from __future__ import annotations

import pytest
from core.integration.enums import ICStatus
from core.integration.models import IntegrationCandidate
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_integrated_sha_cannot_change_after_set(
    db_session,
    sample_project,
    system_ctx,
) -> None:
    from core.domain.delivery_cycles.models import DeliveryCycle
    from core.domain.enums import DeliveryCycleType
    from core.repositories.service import RepositoryService

    repo = await RepositoryService().declare_managed(db_session, sample_project.id, system_ctx)
    sha = "a" * 40
    await RepositoryService().record_materialization(db_session, repo.id, sha, "main", system_ctx)
    cycle = DeliveryCycle(
        project_id=sample_project.id,
        key="C-ic-immut",
        type=DeliveryCycleType.FEATURE_CHANGE,
        objective="ic",
        state="DEVELOPMENT",
        state_version=0,
        opened_by_actor_id=system_ctx.actor.id,
        repository_id=repo.id,
        base_sha=sha,
    )
    db_session.add(cycle)
    await db_session.flush()
    ic = IntegrationCandidate(
        key="IC-001",
        delivery_cycle_id=cycle.id,
        repository_id=repo.id,
        base_sha=sha,
        integration_branch="olympus/integration/IC-001",
        status=ICStatus.VALIDATING,
        ordering=[],
        integrated_sha=sha,
    )
    db_session.add(ic)
    await db_session.flush()
    ic.integrated_sha = "b" * 40
    with pytest.raises(DBAPIError, match="integrated_sha is immutable"):
        await db_session.flush()
