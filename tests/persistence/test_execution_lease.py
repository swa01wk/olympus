from __future__ import annotations

import asyncio
import uuid

import pytest
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.enums import LeaseState
from core.domain.executions.models import ExecutionLease
from core.execution.leases.manager import LeaseManager
from core.scheduler.admission import AdmissionService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.execution_harness import seed_ready_task

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_concurrent_claim_one_wins(async_engine) -> None:
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    task_id = None
    actor_id = None
    async with factory() as session, session.begin():
        bundle = await seed_ready_task(session, key_prefix="lease-excl")
        task_id = bundle.task.id
        actor_id = bundle.actor.id
        ctx = CommandContext(actor=bundle.actor, correlation_id="adm")
        await AdmissionService().admit_task(session, task_id, ctx)

    leases: list[ExecutionLease | None] = []

    async def claim_once() -> None:
        async with factory() as session, session.begin():
            actor = await session.get(Actor, actor_id)
            assert actor is not None
            ctx = CommandContext(actor=actor, correlation_id=str(uuid.uuid4()))
            lease = await LeaseManager().claim(session, f"w-{uuid.uuid4().hex[:4]}", ctx)
            leases.append(lease)

    await asyncio.gather(claim_once(), claim_once())
    winners = [lease for lease in leases if lease is not None]
    assert len(winners) == 1
    assert winners[0].state == LeaseState.ACTIVE

    async with factory() as session:
        active = await session.execute(
            select(ExecutionLease).where(ExecutionLease.state == LeaseState.ACTIVE)
        )
        assert len(list(active.scalars())) == 1
