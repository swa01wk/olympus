from __future__ import annotations

import pytest
from core.intelligence.brownfield.models import RepositoryDiscovery
from core.traceability.models import RepositoryIndexPointer
from sqlalchemy import select
from tests.fixtures.brownfield_harness import brownfield_cycle_at_code_index

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_discovery_facts_and_index_sha(db_session, system_ctx) -> None:
    cycle, sha, repo_id = await brownfield_cycle_at_code_index(db_session, system_ctx)
    discovery = (
        await db_session.execute(
            select(RepositoryDiscovery).where(RepositoryDiscovery.delivery_cycle_id == cycle.id)
        )
    ).scalar_one()
    frameworks = discovery.content.get("frameworks") or []
    assert "fastapi" in frameworks
    assert "sqlalchemy" in frameworks
    assert "pytest" in frameworks
    assert discovery.commit_sha == sha
    assert cycle.base_sha == sha
    pointer = await db_session.get(RepositoryIndexPointer, repo_id)
    assert pointer is not None and pointer.canonical_index_version_id is not None
