"""Reproduction artifacts are content-addressed (Phase 15 persistence §12)."""

from __future__ import annotations

from pathlib import Path

import pytest
from core.execution.artifacts import ArtifactStore
from tests.journey.seed import seed_trusted_project

REPO = (
    Path(__file__).resolve().parents[1] / "fixtures" / "repos" / "supportdesk_defect_closed_update"
)
SEED = Path(__file__).resolve().parents[1] / "fixtures" / "supportdesk" / "trusted_seed_defect.yaml"


@pytest.mark.persistence
@pytest.mark.asyncio
async def test_reproduction_artifact_content_hash_deduplicated(db_session, system_ctx) -> None:
    trusted = await seed_trusted_project(db_session, REPO, SEED, system_ctx)
    store = ArtifactStore()
    payload = {
        "relative_path": "tests/olympus_repro/test_x.py",
        "test_source": "def test_x(): assert False\n",
    }
    a1 = await store.put(
        db_session,
        project_id=trusted.project_id,
        delivery_cycle_id=None,
        execution_id=None,
        kind="REPRODUCTION_TEST",
        schema_name="reproduction_test",
        schema_version="1",
        content=payload,
        created_by_actor_id=system_ctx.actor.id,
    )
    a2 = await store.put(
        db_session,
        project_id=trusted.project_id,
        delivery_cycle_id=None,
        execution_id=None,
        kind="REPRODUCTION_TEST",
        schema_name="reproduction_test",
        schema_version="1",
        content=payload,
        created_by_actor_id=system_ctx.actor.id,
    )
    assert a1.content_hash == a2.content_hash
    assert a1.storage_ref == a2.storage_ref
    assert a1.id != a2.id
