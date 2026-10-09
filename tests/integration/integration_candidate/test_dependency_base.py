from __future__ import annotations

import pytest
from core.assurance.models import Finding
from core.domain.enums import TaskStatus
from core.domain.tasks.models import TaskDependency
from core.integration.dependency_base import DependencyBaseResolver
from sqlalchemy import select
from tests.fixtures.integration_harness import (
    add_implementation_code_task,
    attach_product_lineage,
    commit_files_in_worktree,
    seed_integration_fixture,
)

pytestmark = [pytest.mark.integration, pytest.mark.git]


@pytest.mark.asyncio
async def test_multi_dependency_task_gets_merged_depbase(
    db_session,
    system_ctx,
) -> None:
    fixture = await seed_integration_fixture(db_session, system_ctx, project_key="ic-dep")
    dep1 = await add_implementation_code_task(
        db_session,
        system_ctx,
        fixture,
        title="Dep one",
        key_prefix="dep1",
    )
    await commit_files_in_worktree(
        db_session,
        system_ctx,
        dep1,
        {"src/dep_one.py": "def dep_one():\n    return 1\n"},
    )
    dep2 = await add_implementation_code_task(
        db_session,
        system_ctx,
        fixture,
        title="Dep two",
        key_prefix="dep2",
    )
    await commit_files_in_worktree(
        db_session,
        system_ctx,
        dep2,
        {"src/dep_two.py": "def dep_two():\n    return 2\n"},
    )
    dependent = await add_implementation_code_task(
        db_session,
        system_ctx,
        fixture,
        title="Dependent",
        key_prefix="dep3",
    )
    await attach_product_lineage(db_session, fixture, dependent.task)
    db_session.add(TaskDependency(task_id=dependent.task.id, depends_on_task_id=dep1.task.id))
    db_session.add(TaskDependency(task_id=dependent.task.id, depends_on_task_id=dep2.task.id))
    await db_session.flush()

    resolution = await DependencyBaseResolver().resolve(
        db_session,
        dependent.task,
        fixture.repository.id,
        system_ctx,
    )
    assert resolution.policy == "DEPENDENCY_INTEGRATION"
    assert resolution.base_commit is not None
    assert resolution.commit_available is True
    shas = resolution.inputs.get("shas", [])
    assert isinstance(shas, list)
    assert len(shas) == 2
    assert resolution.inputs.get("branch", "").startswith("olympus/depbase/")


@pytest.mark.asyncio
async def test_single_dependency_task_is_based_on_its_candidate_commit(
    db_session,
    system_ctx,
) -> None:
    fixture = await seed_integration_fixture(db_session, system_ctx, project_key="ic-dep-1")
    dep = await add_implementation_code_task(
        db_session,
        system_ctx,
        fixture,
        title="Only dep",
        key_prefix="dep1s",
    )
    dep_sha = await commit_files_in_worktree(
        db_session,
        system_ctx,
        dep,
        {"src/only_dep.py": "def only_dep():\n    return 1\n"},
    )
    dependent = await add_implementation_code_task(
        db_session,
        system_ctx,
        fixture,
        title="Single dependent",
        key_prefix="dep2s",
    )
    db_session.add(TaskDependency(task_id=dependent.task.id, depends_on_task_id=dep.task.id))
    await db_session.flush()

    resolution = await DependencyBaseResolver().resolve(
        db_session,
        dependent.task,
        fixture.repository.id,
        system_ctx,
    )
    assert resolution.policy == "DEPENDENCY_INTEGRATION"
    assert resolution.base_commit == dep_sha
    assert resolution.commit_available is True
    assert resolution.inputs.get("shas") == [dep_sha]


@pytest.mark.asyncio
async def test_dependency_base_conflict_creates_finding(
    db_session,
    system_ctx,
) -> None:
    fixture = await seed_integration_fixture(db_session, system_ctx, project_key="ic-dep-c")
    shared = "src/shared_dep.py"
    dep1 = await add_implementation_code_task(
        db_session,
        system_ctx,
        fixture,
        title="Dep A",
        key_prefix="dca1",
    )
    await commit_files_in_worktree(
        db_session,
        system_ctx,
        dep1,
        {shared: "value = 'a'\n"},
    )
    dep2 = await add_implementation_code_task(
        db_session,
        system_ctx,
        fixture,
        title="Dep B",
        key_prefix="dca2",
    )
    await commit_files_in_worktree(
        db_session,
        system_ctx,
        dep2,
        {shared: "value = 'b'\n"},
    )
    dependent = await add_implementation_code_task(
        db_session,
        system_ctx,
        fixture,
        title="Dependent conflict",
        key_prefix="dca3",
    )
    db_session.add(TaskDependency(task_id=dependent.task.id, depends_on_task_id=dep1.task.id))
    db_session.add(TaskDependency(task_id=dependent.task.id, depends_on_task_id=dep2.task.id))
    await db_session.flush()

    with pytest.raises(ValueError, match="DEPENDENCY_BASE_CONFLICT"):
        await DependencyBaseResolver().resolve(
            db_session,
            dependent.task,
            fixture.repository.id,
            system_ctx,
        )
    finding = (
        await db_session.execute(
            select(Finding).where(
                Finding.delivery_cycle_id == fixture.cycle.id,
                Finding.category == "DEPENDENCY_BASE_CONFLICT",
            )
        )
    ).scalar_one()
    assert finding.blocking is True
    assert dependent.task.status != TaskStatus.COMPLETED
