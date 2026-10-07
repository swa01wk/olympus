from __future__ import annotations

import pytest
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind, ActorRole, RevisionCause
from core.domain.repositories.models import RepositoryRevision
from core.integration.enums import ICStatus
from core.state.transition_service import TransitionService
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
async def test_cancel_cycle_reverts_held_canonical_revision(
    db_session,
    system_ctx,
) -> None:
    fixture = await seed_integration_fixture(db_session, system_ctx, project_key="ic-revert")
    git_dir = await git_dir_for_repository(db_session, fixture.repository.id)
    default_head = await default_branch_head(git_dir)
    bundle = await add_implementation_code_task(
        db_session,
        system_ctx,
        fixture,
        title="Task",
        key_prefix="rev1",
    )
    await commit_files_in_worktree(
        db_session,
        system_ctx,
        bundle,
        {"src/revert.py": "def revert_me():\n    return 0\n"},
    )
    ic = await create_and_run_integration(db_session, system_ctx, fixture.cycle.id)
    assert ic.status == ICStatus.READY
    await db_session.refresh(fixture.repository)
    assert fixture.repository.canonical_commit == ic.integrated_sha

    human = Actor(kind=ActorKind.HUMAN, name="operator", roles=[ActorRole.OPERATOR.value])
    db_session.add(human)
    await db_session.flush()
    from core.commands.context import CommandContext

    human_ctx = CommandContext(actor=human, correlation_id="cancel-cycle")
    await TransitionService().transition(
        db_session,
        "delivery_cycle",
        fixture.cycle.id,
        fixture.cycle.state,
        "cancel",
        human_ctx,
        payload={"reason": "test cancel"},
    )

    await db_session.refresh(fixture.repository)
    assert fixture.repository.canonical_commit == default_head
    await db_session.refresh(ic)
    assert ic.status == ICStatus.SUPERSEDED

    reverted = (
        await db_session.execute(
            select(RepositoryRevision).where(
                RepositoryRevision.repository_id == fixture.repository.id,
                RepositoryRevision.cause == RevisionCause.REVERTED,
            )
        )
    ).scalar_one()
    assert reverted.commit_sha == default_head
