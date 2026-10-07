from __future__ import annotations

import subprocess

import pytest
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import DeliveryCycleType
from core.domain.projects.models import Project
from core.intelligence.brownfield.models import RepositoryDiscovery
from core.intelligence.code_index.models import CodeIndexVersion
from sqlalchemy import select
from tests.fixtures.code_index_harness import SUPPORTDESK_R1
from tests.fixtures.repositories import materialize_fixture_repository

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_clone_binding_immutable_after_origin_moves(
    db_session,
    system_ctx,
    tmp_path,
) -> None:
    origin = tmp_path / "origin"
    subprocess.run(["cp", "-R", str(SUPPORTDESK_R1), str(origin)], check=True)
    project = Project(key="bf-bind", name="BF Bind")
    db_session.add(project)
    await db_session.flush()
    repo, head = await materialize_fixture_repository(db_session, project, origin, system_ctx)
    cycle = await DeliveryCycleService().create(
        db_session,
        project.id,
        DeliveryCycleType.BROWNFIELD_ONBOARDING,
        "bind",
        system_ctx,
        repository_id=repo.id,
    )
    from core.state.transition_service import TransitionService

    await TransitionService().transition(
        db_session,
        "delivery_cycle",
        cycle.id,
        cycle.state,
        "start_code_index",
        system_ctx,
    )
    if not (origin / ".git").exists():
        subprocess.run(["git", "init"], cwd=origin, check=True, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=origin, check=True, capture_output=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "init"],
            cwd=origin,
            check=True,
            capture_output=True,
        )
    (origin / "after_clone.txt").write_text("later\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=origin, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "after"],
        cwd=origin,
        check=True,
        capture_output=True,
    )
    refreshed = await db_session.get(DeliveryCycle, cycle.id)
    assert refreshed is not None
    assert refreshed.base_sha == head
    discovery = (
        await db_session.execute(
            select(RepositoryDiscovery).where(RepositoryDiscovery.delivery_cycle_id == cycle.id)
        )
    ).scalar_one()
    assert discovery.commit_sha == head
    index = (
        (
            await db_session.execute(
                select(CodeIndexVersion).where(CodeIndexVersion.commit_sha == head)
            )
        )
        .scalars()
        .first()
    )
    assert index is not None
