from __future__ import annotations

import pytest
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import ActorKind, ActorRole, DeliveryCycleType, TaskOrigin, WorkType
from core.domain.exceptions import DomainError
from core.domain.projects.models import Project
from core.domain.tasks.service import TaskService
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_dependency_cycle_rejected(db_session: AsyncSession) -> None:
    actor = Actor(kind=ActorKind.HUMAN, name="dep-test", roles=[ActorRole.OPERATOR.value])
    db_session.add(actor)
    project = Project(key="dep-p", name="Dep")
    db_session.add(project)
    await db_session.flush()
    ctx = CommandContext(actor=actor, correlation_id="c1")
    cycle = await DeliveryCycleService().create(
        db_session,
        project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "obj",
        ctx,
    )
    ts = TaskService()
    t1 = await ts.create_task(
        db_session, cycle.id, "A", WorkType.ANALYSIS, TaskOrigin.CONTROL_PLANE, ctx
    )
    t2 = await ts.create_task(
        db_session, cycle.id, "B", WorkType.ANALYSIS, TaskOrigin.CONTROL_PLANE, ctx
    )
    t3 = await ts.create_task(
        db_session, cycle.id, "C", WorkType.ANALYSIS, TaskOrigin.CONTROL_PLANE, ctx
    )
    await ts.add_dependency(db_session, t1.id, t2.id)
    await ts.add_dependency(db_session, t2.id, t3.id)
    with pytest.raises(DomainError) as exc:
        await ts.add_dependency(db_session, t3.id, t1.id)
    assert exc.value.code == "DEPENDENCY_CYCLE"
