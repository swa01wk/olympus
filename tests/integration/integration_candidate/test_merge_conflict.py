from __future__ import annotations

import pytest
from core.assurance.models import Finding
from core.domain.enums import TaskStatus, WorkType
from core.domain.tasks.models import Task
from core.integration.enums import ICStatus
from sqlalchemy import select
from tests.fixtures.integration_harness import (
    add_implementation_code_task,
    commit_files_in_worktree,
    create_and_run_integration,
    default_branch_head,
    git_dir_for_repository,
    seed_integration_fixture,
)

pytestmark = [pytest.mark.integration, pytest.mark.git]


@pytest.mark.asyncio
async def test_conflicting_candidates_produce_finding_and_remediation(
    db_session,
    system_ctx,
) -> None:
    fixture = await seed_integration_fixture(db_session, system_ctx, project_key="ic-conflict")
    git_dir = await git_dir_for_repository(db_session, fixture.repository.id)
    main_before = await default_branch_head(git_dir)

    conflict_path = "src/shared.py"
    bundle1 = await add_implementation_code_task(
        db_session,
        system_ctx,
        fixture,
        title="Task one",
        key_prefix="cf1",
    )
    await commit_files_in_worktree(
        db_session,
        system_ctx,
        bundle1,
        {conflict_path: "value = 'task-one'\n"},
    )
    bundle2 = await add_implementation_code_task(
        db_session,
        system_ctx,
        fixture,
        title="Task two",
        key_prefix="cf2",
    )
    await commit_files_in_worktree(
        db_session,
        system_ctx,
        bundle2,
        {conflict_path: "value = 'task-two'\n"},
    )

    ic = await create_and_run_integration(db_session, system_ctx, fixture.cycle.id)
    assert ic.status == ICStatus.CONFLICT
    assert ic.integrated_sha is None

    finding = (
        await db_session.execute(
            select(Finding).where(
                Finding.integration_candidate_id == ic.id,
                Finding.category == "MERGE_CONFLICT",
            )
        )
    ).scalar_one()
    assert finding.remediation_task_id is not None
    remediation = await db_session.get(Task, finding.remediation_task_id)
    assert remediation is not None
    assert remediation.work_type == WorkType.CODE_CHANGE
    assert remediation.origin.value == "REMEDIATION"
    assert remediation.status == TaskStatus.READY

    main_after = await default_branch_head(git_dir)
    assert main_before == main_after
