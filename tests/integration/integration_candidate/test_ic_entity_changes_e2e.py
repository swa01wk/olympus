from __future__ import annotations

import pytest
from core.traceability.models import CodeEntityChange
from sqlalchemy import select
from tests.fixtures.integration_harness import (
    add_implementation_code_task,
    commit_files_in_worktree,
    create_and_run_integration,
    seed_integration_fixture,
)

pytestmark = [pytest.mark.integration, pytest.mark.git]


@pytest.mark.asyncio
async def test_entity_changes_record_task_execution_and_commit(
    db_session,
    system_ctx,
) -> None:
    fixture = await seed_integration_fixture(db_session, system_ctx, project_key="ic-changes")
    bundle = await add_implementation_code_task(
        db_session,
        system_ctx,
        fixture,
        title="Change task",
        key_prefix="chg1",
    )
    sha = await commit_files_in_worktree(
        db_session,
        system_ctx,
        bundle,
        {"src/changed.py": "def changed():\n    return 'ok'\n"},
    )
    ic = await create_and_run_integration(db_session, system_ctx, fixture.cycle.id)
    assert ic.integrated_sha is not None

    rows = (
        (
            await db_session.execute(
                select(CodeEntityChange).where(CodeEntityChange.integration_candidate_id == ic.id)
            )
        )
        .scalars()
        .all()
    )
    assert rows
    row = rows[0]
    assert row.task_id == bundle.task.id
    assert row.execution_id == bundle.execution_bundle.execution.id
    assert row.candidate_commit_sha == sha
    assert row.integrated_sha == ic.integrated_sha
