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


@pytest.mark.asyncio
async def test_remediation_starts_from_conflict_markers_and_resolution_integrates(
    db_session,
    system_ctx,
) -> None:
    from core.domain.task_contracts.models import TaskContract
    from core.execution.worktrees.git import GitCli

    fixture = await seed_integration_fixture(db_session, system_ctx, project_key="ic-resolve")
    git_dir = await git_dir_for_repository(db_session, fixture.repository.id)
    path = "src/shared.py"
    for title, prefix, value in (("Task one", "rs1", "one"), ("Task two", "rs2", "two")):
        bundle = await add_implementation_code_task(
            db_session, system_ctx, fixture, title=title, key_prefix=prefix
        )
        await commit_files_in_worktree(
            db_session, system_ctx, bundle, {path: f"value = '{value}'\n"}
        )

    ic = await create_and_run_integration(db_session, system_ctx, fixture.cycle.id)
    assert ic.status == ICStatus.CONFLICT
    finding = (
        await db_session.execute(
            select(Finding).where(
                Finding.integration_candidate_id == ic.id, Finding.category == "MERGE_CONFLICT"
            )
        )
    ).scalar_one()
    assert finding.detail["conflicting_files"] == [path]
    conflict_sha = finding.detail["conflict_sha"]
    assert conflict_sha

    remediation = await db_session.get(Task, finding.remediation_task_id)
    assert remediation is not None
    contract = await db_session.get(TaskContract, remediation.current_contract_id)
    assert contract is not None
    assert contract.body["base_commit"] == conflict_sha
    assert contract.body["allowed_scope"] == [path]
    assert {"repo.list", "git.status"} <= set(contract.body["allowed_actions"])
    marked = GitCli().run(["show", f"{conflict_sha}:{path}"], git_dir=git_dir).stdout
    assert "<<<<<<<" in marked and ">>>>>>>" in marked

    # Stand in for the agent: resolve on top of the conflict commit, then integrate again.
    remediation.status = TaskStatus.CANCELLED
    fixer = await add_implementation_code_task(
        db_session,
        system_ctx,
        fixture,
        title="Resolve",
        key_prefix="rs3",
        base_sha=conflict_sha,
    )
    await commit_files_in_worktree(db_session, system_ctx, fixer, {path: "value = 'one and two'\n"})
    again = await create_and_run_integration(db_session, system_ctx, fixture.cycle.id)
    assert again.status != ICStatus.CONFLICT, again.status
    assert again.integrated_sha
    merged = GitCli().run(["show", f"{again.integrated_sha}:{path}"], git_dir=git_dir).stdout
    assert merged == "value = 'one and two'\n"


@pytest.mark.asyncio
async def test_recheck_candidate_on_already_integrated_code_reaches_ready(
    db_session,
    system_ctx,
) -> None:
    """Autopilot's re-check builds a new candidate from the same commits; it must settle READY."""
    fixture = await seed_integration_fixture(db_session, system_ctx, project_key="ic-recheck")
    bundle = await add_implementation_code_task(
        db_session, system_ctx, fixture, title="Only task", key_prefix="rc1"
    )
    await commit_files_in_worktree(db_session, system_ctx, bundle, {"src/a.py": "A = 1\n"})
    first = await create_and_run_integration(db_session, system_ctx, fixture.cycle.id)
    assert first.status == ICStatus.READY, first.status

    again = await create_and_run_integration(db_session, system_ctx, fixture.cycle.id)
    assert again.id != first.id
    assert again.status == ICStatus.READY, again.status
    assert again.supersedes_id == first.id
    assert again.integrated_sha == first.integrated_sha
