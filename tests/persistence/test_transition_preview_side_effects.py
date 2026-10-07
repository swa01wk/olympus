from __future__ import annotations

import uuid

import pytest
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import DeliveryCycleType
from core.domain.projects.models import Project
from core.state.preview import TransitionPreviewService
from sqlalchemy import func, select


@pytest.mark.asyncio
async def test_preview_does_not_mutate_state_version(db_session, system_actor) -> None:
    project = Project(key=f"P{uuid.uuid4().hex[:8]}", name="Preview")
    db_session.add(project)
    await db_session.flush()
    cycle = DeliveryCycle(
        project_id=project.id,
        key="DC-1",
        type=DeliveryCycleType.GREENFIELD_BUILD,
        objective="preview",
        state="PLANNING",
        state_version=3,
        opened_by_actor_id=system_actor.id,
    )
    db_session.add(cycle)
    await db_session.flush()
    before = cycle.state_version
    ctx = CommandContext(
        actor=system_actor,
        correlation_id="test",
        idempotency_key=str(uuid.uuid4()),
    )
    previews = await TransitionPreviewService().preview_delivery_cycle(db_session, cycle, ctx)
    assert previews
    await db_session.refresh(cycle)
    assert cycle.state_version == before
    count = (await db_session.execute(select(func.count()).select_from(DeliveryCycle))).scalar_one()
    assert count >= 1
