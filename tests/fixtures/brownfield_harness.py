from __future__ import annotations

import uuid

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import DeliveryCycleType
from core.domain.projects.models import Project
from sqlalchemy.ext.asyncio import AsyncSession
from tests.fixtures.code_index_harness import materialize_supportdesk_r1


async def brownfield_cycle_at_code_index(
    session: AsyncSession,
    ctx: CommandContext,
) -> tuple[DeliveryCycle, str, uuid.UUID]:
    repo, sha = await materialize_supportdesk_r1(session, ctx)
    project = await session.get(Project, repo.project_id)
    assert project is not None
    cycle = await DeliveryCycleService().create(
        session,
        project.id,
        DeliveryCycleType.BROWNFIELD_ONBOARDING,
        "Onboard SupportDesk",
        ctx,
        repository_id=repo.id,
    )
    cycle.base_sha = sha
    await session.flush()
    from core.state.transition_service import TransitionService

    await TransitionService().transition(
        session,
        "delivery_cycle",
        cycle.id,
        cycle.state,
        "start_code_index",
        ctx,
    )
    refreshed = await session.get(DeliveryCycle, cycle.id)
    assert refreshed is not None
    return refreshed, sha, repo.id
