from __future__ import annotations

import uuid

import pytest
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import DeliveryCycleType
from core.domain.exceptions import DomainError
from core.integration.service import IntegrationService
from core.repositories.revision import RepositoryRevisionService
from tests.fixtures.integration_harness import (
    add_implementation_code_task,
    commit_files_in_worktree,
    create_and_run_integration,
    seed_integration_fixture,
)

pytestmark = [pytest.mark.integration, pytest.mark.git]


@pytest.mark.asyncio
async def test_unreleased_canonical_blocks_other_cycle_ic_create(
    db_session,
    system_ctx,
) -> None:
    fixture_a = await seed_integration_fixture(db_session, system_ctx, project_key="ic-lock-a")
    bundle_a = await add_implementation_code_task(
        db_session,
        system_ctx,
        fixture_a,
        title="Cycle A task",
        key_prefix="lock-a",
    )
    await commit_files_in_worktree(
        db_session,
        system_ctx,
        bundle_a,
        {"src/a.py": "def a():\n    return 1\n"},
    )
    ic_a = await create_and_run_integration(db_session, system_ctx, fixture_a.cycle.id)
    assert ic_a.integrated_sha is not None
    integrated_sha = ic_a.integrated_sha

    cycle_b = DeliveryCycle(
        project_id=fixture_a.project.id,
        key="C-ic-lock-b",
        type=DeliveryCycleType.FEATURE_CHANGE,
        objective="second cycle",
        state="DEVELOPMENT",
        state_version=0,
        opened_by_actor_id=system_ctx.actor.id,
        repository_id=fixture_a.repository.id,
        base_sha=integrated_sha,
    )
    db_session.add(cycle_b)
    await db_session.flush()
    fixture_b = type(fixture_a)(
        project=fixture_a.project,
        repository=fixture_a.repository,
        cycle=cycle_b,
        base_sha=integrated_sha,
    )
    bundle_b = await add_implementation_code_task(
        db_session,
        system_ctx,
        fixture_b,
        title="Cycle B task",
        key_prefix="lock-b",
        base_sha=integrated_sha,
    )
    await commit_files_in_worktree(
        db_session,
        system_ctx,
        bundle_b,
        {"src/b.py": "def b():\n    return 2\n"},
    )

    with pytest.raises(DomainError) as exc:
        await IntegrationService().create(db_session, cycle_b.id, system_ctx)
    assert exc.value.code == "CANONICAL_REVISION_HELD"

    await RepositoryRevisionService().mark_released(
        db_session,
        fixture_a.repository.id,
        integrated_sha,
        uuid.uuid4(),
        system_ctx,
    )
    ic_b = await IntegrationService().create(db_session, cycle_b.id, system_ctx)
    assert ic_b.base_sha == integrated_sha
