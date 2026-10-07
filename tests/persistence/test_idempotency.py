from __future__ import annotations

import pytest
from core.commands.command_log import begin_command, complete_command
from core.commands.context import CommandContext
from core.domain.delivery_cycles.service import DeliveryCycleService
from core.domain.enums import DeliveryCycleType
from core.domain.exceptions import IdempotencyConflict

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_idempotent_create_replays(db_session, sample_project, system_actor) -> None:
    ctx = CommandContext(
        actor=system_actor,
        correlation_id="idem",
        idempotency_key="create-cycle-1",
    )
    payload = {"type": "GREENFIELD_BUILD", "objective": "same"}
    log = await begin_command(
        db_session,
        command_name="create_delivery_cycle",
        target_type="project",
        target_id=str(sample_project.id),
        actor_id=system_actor.id,
        idempotency_key=ctx.idempotency_key,
        request_body=payload,
        correlation_id=ctx.correlation_id,
    )
    assert log is not None
    cycle = await DeliveryCycleService().create(
        db_session,
        sample_project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "same",
        ctx,
    )
    await complete_command(db_session, log, {"cycle_id": str(cycle.id)})
    replay = await begin_command(
        db_session,
        command_name="create_delivery_cycle",
        target_type="project",
        target_id=str(sample_project.id),
        actor_id=system_actor.id,
        idempotency_key=ctx.idempotency_key,
        request_body=payload,
        correlation_id=ctx.correlation_id,
    )
    assert replay is not None
    assert replay.result == {"cycle_id": str(cycle.id)}


@pytest.mark.asyncio
async def test_idempotency_key_conflict(db_session, sample_project, system_actor) -> None:
    key = "key-conflict"
    base = {"type": "GREENFIELD_BUILD", "objective": "a"}
    await begin_command(
        db_session,
        command_name="create_delivery_cycle",
        target_type="project",
        target_id=str(sample_project.id),
        actor_id=system_actor.id,
        idempotency_key=key,
        request_body=base,
        correlation_id="c",
    )
    with pytest.raises(IdempotencyConflict):
        await begin_command(
            db_session,
            command_name="create_delivery_cycle",
            target_type="project",
            target_id=str(sample_project.id),
            actor_id=system_actor.id,
            idempotency_key=key,
            request_body={"type": "GREENFIELD_BUILD", "objective": "different"},
            correlation_id="c",
        )
