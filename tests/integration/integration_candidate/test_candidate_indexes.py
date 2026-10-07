from __future__ import annotations

import pytest
from core.integration.enums import ICStatus
from core.intelligence.code_index.enums import IndexKind, IndexVersionStatus
from core.intelligence.code_index.models import CodeIndexVersion
from core.traceability.models import RepositoryIndexPointer
from sqlalchemy import select
from tests.fixtures.integration_harness import (
    add_implementation_code_task,
    commit_files_in_worktree,
    create_and_run_integration,
    seed_integration_fixture,
)

pytestmark = [pytest.mark.integration, pytest.mark.git]


@pytest.mark.asyncio
async def test_candidate_indexes_discarded_and_never_pointed(
    db_session,
    system_ctx,
) -> None:
    fixture = await seed_integration_fixture(db_session, system_ctx, project_key="ic-idx")
    bundle = await add_implementation_code_task(
        db_session,
        system_ctx,
        fixture,
        title="Index task",
        key_prefix="idx1",
    )
    sha = await commit_files_in_worktree(
        db_session,
        system_ctx,
        bundle,
        {"src/indexed.py": "def indexed():\n    return True\n"},
    )

    candidate = (
        await db_session.execute(
            select(CodeIndexVersion).where(
                CodeIndexVersion.repository_id == fixture.repository.id,
                CodeIndexVersion.commit_sha == sha,
                CodeIndexVersion.kind == IndexKind.CANDIDATE,
            )
        )
    ).scalar_one()
    assert candidate.status == IndexVersionStatus.READY

    pointer_before = await db_session.get(RepositoryIndexPointer, fixture.repository.id)
    assert pointer_before is None or pointer_before.canonical_index_version_id != candidate.id

    ic = await create_and_run_integration(db_session, system_ctx, fixture.cycle.id)
    assert ic.status == ICStatus.READY

    await db_session.refresh(candidate)
    assert candidate.status == IndexVersionStatus.DISCARDED

    pointer = await db_session.get(RepositoryIndexPointer, fixture.repository.id)
    assert pointer is not None
    assert pointer.canonical_index_version_id != candidate.id
