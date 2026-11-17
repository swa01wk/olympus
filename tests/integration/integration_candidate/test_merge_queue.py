"""Merge queue: tasks start from all finished code, and failed checks get fixed, not stuck."""

from __future__ import annotations

import pytest
from core.assurance.models import Finding
from core.domain.enums import ExecutionStatus, TaskStatus
from core.domain.executions.models import Execution
from core.domain.task_contracts.models import TaskContract
from core.domain.tasks.models import Task
from core.execution.worktrees.git import GitCli
from core.integration.enums import FindingStatus, ICStatus
from core.integration.queue_tip import QueueTipResolver
from core.integration.remediation import MAX_AUTO_CHECK_FIXES
from sqlalchemy import select
from tests.fixtures.integration_harness import (
    add_implementation_code_task,
    commit_files_in_worktree,
    create_and_run_integration,
    git_dir_for_repository,
    seed_integration_fixture,
)

pytestmark = [pytest.mark.integration, pytest.mark.git]


async def _tip(db_session, fixture, task: Task):  # type: ignore[no-untyped-def]
    return await QueueTipResolver().resolve(db_session, task, fixture.repository.id)


@pytest.mark.asyncio
async def test_queue_tip_is_cycle_base_then_latest_finished_work(db_session, system_ctx) -> None:
    fixture = await seed_integration_fixture(db_session, system_ctx, project_key="mq-chain")
    path = "src/shared.py"

    first = await add_implementation_code_task(
        db_session, system_ctx, fixture, title="First", key_prefix="mq1"
    )
    empty = await _tip(db_session, fixture, first.task)
    assert empty.base_commit == fixture.base_sha
    first_sha = await commit_files_in_worktree(
        db_session, system_ctx, first, {path: "value = 'one'\n"}
    )

    # The next task starts from the first one's code, so editing the same line is no conflict.
    second = await add_implementation_code_task(
        db_session, system_ctx, fixture, title="Second", key_prefix="mq2"
    )
    tip = await _tip(db_session, fixture, second.task)
    assert tip.policy == "QUEUE_TIP"
    assert tip.base_commit == first_sha
    assert tip.inputs["heads"] == [first_sha]
    second.task.status = TaskStatus.CANCELLED
    chained = await add_implementation_code_task(
        db_session, system_ctx, fixture, title="Second", key_prefix="mq3", base_sha=first_sha
    )
    second_sha = await commit_files_in_worktree(
        db_session, system_ctx, chained, {path: "value = 'one and two'\n"}
    )

    third = await add_implementation_code_task(
        db_session, system_ctx, fixture, title="Third", key_prefix="mq4"
    )
    assert (await _tip(db_session, fixture, third.task)).base_commit == second_sha

    third.task.status = TaskStatus.CANCELLED
    ic = await create_and_run_integration(db_session, system_ctx, fixture.cycle.id)
    assert ic.status == ICStatus.READY, ic.status
    git_dir = await git_dir_for_repository(db_session, fixture.repository.id)
    merged = GitCli().run(["show", f"{ic.integrated_sha}:{path}"], git_dir=git_dir).stdout
    assert merged == "value = 'one and two'\n"


@pytest.mark.asyncio
async def test_queue_tip_merges_separate_lines_of_work_once(db_session, system_ctx) -> None:
    fixture = await seed_integration_fixture(db_session, system_ctx, project_key="mq-split")
    for title, prefix, path in (("A", "ms1", "src/a.py"), ("B", "ms2", "src/b.py")):
        bundle = await add_implementation_code_task(
            db_session, system_ctx, fixture, title=title, key_prefix=prefix
        )
        await commit_files_in_worktree(db_session, system_ctx, bundle, {path: f"{title} = 1\n"})

    nxt = await add_implementation_code_task(
        db_session, system_ctx, fixture, title="Next", key_prefix="ms3"
    )
    tip = await _tip(db_session, fixture, nxt.task)
    assert len(tip.inputs["heads"]) == 2
    assert "skipped" not in tip.inputs
    git_dir = await git_dir_for_repository(db_session, fixture.repository.id)
    files = GitCli().run(["ls-tree", "-r", "--name-only", str(tip.base_commit)], git_dir=git_dir)
    assert {"src/a.py", "src/b.py"} <= set(files.stdout.split())
    # Resolved again (as every scheduler tick does), the cached merge is reused.
    assert (await _tip(db_session, fixture, nxt.task)).base_commit == tip.base_commit


@pytest.mark.asyncio
async def test_queue_tip_skips_a_conflicting_line_of_work(db_session, system_ctx) -> None:
    fixture = await seed_integration_fixture(db_session, system_ctx, project_key="mq-skip")
    shas = []
    for prefix, value in (("mk1", "one"), ("mk2", "two")):
        bundle = await add_implementation_code_task(
            db_session, system_ctx, fixture, title=value, key_prefix=prefix
        )
        shas.append(
            await commit_files_in_worktree(
                db_session, system_ctx, bundle, {"src/shared.py": f"value = '{value}'\n"}
            )
        )

    nxt = await add_implementation_code_task(
        db_session, system_ctx, fixture, title="Next", key_prefix="mk3"
    )
    tip = await _tip(db_session, fixture, nxt.task)
    assert tip.base_commit == shas[0]
    assert tip.inputs["skipped"] == [shas[1]]
    assert (await _tip(db_session, fixture, nxt.task)).inputs["skipped"] == [shas[1]]


async def _check_finding(db_session, ic_id):  # type: ignore[no-untyped-def]
    return (
        await db_session.execute(
            select(Finding).where(
                Finding.integration_candidate_id == ic_id,
                Finding.category == "INTEGRATION_CHECK_FAILED",
            )
        )
    ).scalar_one()


@pytest.mark.asyncio
async def test_failed_checks_get_a_fix_task_on_the_merged_code_until_the_cap(
    db_session, system_ctx
) -> None:
    fixture = await seed_integration_fixture(db_session, system_ctx, project_key="mq-checks")
    bundle = await add_implementation_code_task(
        db_session, system_ctx, fixture, title="Breaks tests", key_prefix="mc1"
    )
    await commit_files_in_worktree(
        db_session,
        system_ctx,
        bundle,
        {"tests/test_broken.py": "def test_broken():\n    assert 1 == 2\n"},
    )

    for round_no in range(MAX_AUTO_CHECK_FIXES + 1):
        ic = await create_and_run_integration(db_session, system_ctx, fixture.cycle.id)
        assert ic.status == ICStatus.FAILED, ic.status
        execution = await db_session.get(Execution, ic.integration_execution_id)
        assert execution is not None
        assert execution.status == ExecutionStatus.FAILED
        assert execution.retriable is False  # same commits, same verdict: fix, don't rerun
        integration_task = await db_session.get(Task, execution.task_id)
        assert integration_task is not None
        assert integration_task.status == TaskStatus.FAILED

        finding = await _check_finding(db_session, ic.id)
        head = finding.detail["merged_head_sha"]
        assert "FAILED tests/test_broken.py::test_broken" in finding.detail["summary"]
        if round_no == MAX_AUTO_CHECK_FIXES:
            # Out of automatic rounds: left open for the person (Autopilot offers Try again).
            assert finding.status == FindingStatus.OPEN
            assert finding.remediation_task_id is None
            break
        assert finding.status == FindingStatus.IN_REMEDIATION
        assert finding.detail["auto_fix"] is True
        fix = await db_session.get(Task, finding.remediation_task_id)
        assert fix is not None
        assert fix.status == TaskStatus.READY
        contract = await db_session.get(TaskContract, fix.current_contract_id)
        assert contract is not None
        assert contract.body["base_policy"] == "EXPLICIT_SHA"
        assert contract.body["base_commit"] == head
        assert contract.body["allowed_scope"] == ["**"]
        assert "FAILED tests/test_broken.py::test_broken" in contract.body["objective"]
        # Stand in for a fix attempt that did not help, so the next round fails again.
        fix.status = TaskStatus.CANCELLED
        await db_session.flush()
