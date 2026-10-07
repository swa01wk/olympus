import pytest
from core.domain.canonical_json import sha256_hex
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import DeliveryCycleType, SpecStatus
from core.planning.models import Architecture
from core.state.guards import guard_registry
from tests.fixtures.planning_harness import supportdesk_architecture_proposal

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_architecture_approved_guard(db_session) -> None:
    from core.domain.actors.models import Actor
    from core.domain.enums import ActorKind, ActorRole
    from core.domain.projects.models import Project

    actor = Actor(kind=ActorKind.SYSTEM, name="guard-test", roles=[ActorRole.SYSTEM.value])
    db_session.add(actor)
    await db_session.flush()
    project = Project(key="plan-guard", name="Plan Guard")
    db_session.add(project)
    await db_session.flush()
    cycle = DeliveryCycle(
        project_id=project.id,
        key="C-GUARD",
        type=DeliveryCycleType.GREENFIELD_BUILD,
        objective="g",
        state="ARCHITECTURE",
        state_version=0,
        opened_by_actor_id=actor.id,
    )
    db_session.add(cycle)
    await db_session.flush()
    result = await guard_registry.evaluate("architecture_approved", db_session, cycle, None)
    assert not result.ok
    body = supportdesk_architecture_proposal().body.model_dump(mode="json")
    db_session.add(
        Architecture(
            project_id=project.id,
            lineage_key="ARCH",
            version=1,
            status=SpecStatus.APPROVED,
            kind="BASELINE",
            body=body,
            content_hash=sha256_hex(body),
        )
    )
    await db_session.flush()
    result = await guard_registry.evaluate("architecture_approved", db_session, cycle, None)
    assert result.ok
