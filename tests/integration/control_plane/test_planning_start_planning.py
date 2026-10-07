from __future__ import annotations

import pytest
from core.domain.connectors.models import ConnectorActionRecord
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import DeliveryCycleType, RepositoryStatus
from core.domain.events.models import DomainEvent
from core.domain.exceptions import GuardFailed
from core.domain.repositories.models import Repository
from sqlalchemy import func, select
from tests.fixtures.planning_workflow_harness import (
    provision_greenfield_repository,
    seed_approved_architecture,
)

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_start_planning_blocked_while_repository_provisioning(
    db_session, sample_project, system_ctx
) -> None:
    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "planning gate",
        system_ctx,
    )
    await seed_approved_architecture(db_session, sample_project.id, system_ctx)
    cycle.state = "ARCHITECTURE"
    await db_session.flush()

    with pytest.raises(GuardFailed) as exc:
        await DeliveryCycleService().run_command(
            db_session,
            cycle.id,
            "start_planning",
            "ARCHITECTURE",
            system_ctx,
        )
    assert any("REPOSITORY_NOT_READY:PROVISIONING" in r for r in exc.value.reasons)


@pytest.mark.asyncio
async def test_start_planning_pins_base_sha_after_provision(
    db_session, sample_project, system_ctx
) -> None:
    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "planning pin",
        system_ctx,
    )
    await seed_approved_architecture(db_session, sample_project.id, system_ctx)
    await provision_greenfield_repository(db_session, cycle, system_ctx)
    await db_session.refresh(cycle)
    repo = await db_session.get(Repository, cycle.repository_id)
    assert repo is not None
    assert repo.status == RepositoryStatus.READY
    assert repo.canonical_commit is not None

    cycle.state = "ARCHITECTURE"
    await db_session.flush()

    result = await DeliveryCycleService().run_command(
        db_session,
        cycle.id,
        "start_planning",
        "ARCHITECTURE",
        system_ctx,
    )
    assert result.to_state == "PLANNING"
    await db_session.refresh(cycle)
    await db_session.refresh(repo)
    assert cycle.base_sha == repo.canonical_commit
    assert repo.registered_sha == repo.canonical_commit

    materialized = await db_session.execute(
        select(func.count())
        .select_from(DomainEvent)
        .where(
            DomainEvent.event_type == "repository.materialized",
            DomainEvent.aggregate_id == repo.id,
        )
    )
    assert materialized.scalar_one() >= 1

    init_actions = await db_session.scalar(
        select(func.count())
        .select_from(ConnectorActionRecord)
        .where(ConnectorActionRecord.action == "init_repository")
    )
    assert init_actions and init_actions >= 1


@pytest.mark.asyncio
async def test_start_planning_idempotent_on_repository(
    db_session, sample_project, system_ctx
) -> None:
    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "planning idempotent",
        system_ctx,
    )
    repo_id = cycle.repository_id
    await seed_approved_architecture(db_session, sample_project.id, system_ctx)
    await provision_greenfield_repository(db_session, cycle, system_ctx)
    rev_before = await db_session.scalar(
        select(func.count()).select_from(Repository).where(Repository.id == repo_id)
    )
    cycle.state = "ARCHITECTURE"
    await db_session.flush()
    await DeliveryCycleService().run_command(
        db_session,
        cycle.id,
        "start_planning",
        "ARCHITECTURE",
        system_ctx,
    )
    await db_session.refresh(cycle)
    repo = await db_session.get(Repository, repo_id)
    assert repo is not None
    assert cycle.state == "PLANNING"
    sha_after_planning = repo.canonical_commit
    rev_after = await db_session.scalar(
        select(func.count()).select_from(Repository).where(Repository.id == repo_id)
    )
    assert rev_before == rev_after == 1
    assert sha_after_planning is not None
    await db_session.refresh(repo)
    assert repo.canonical_commit == sha_after_planning
