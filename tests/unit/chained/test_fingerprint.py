"""Canonical fingerprint stability (Phase 19 §12)."""

from __future__ import annotations

import uuid

import pytest
from core.commands.context import CommandContext
from core.domain.projects.models import Project
from scripts.demo.chained.restart import canonical_fingerprint
from sqlalchemy.ext.asyncio import AsyncSession
from tests.fixtures.planning_workflow_harness import ensure_system_actor


@pytest.mark.persistence
@pytest.mark.asyncio
async def test_fingerprint_stable_for_same_state(db_session: AsyncSession) -> None:
    actor = await ensure_system_actor(db_session)
    project = Project(key=f"FP-{uuid.uuid4().hex[:6]}", name="fp")
    db_session.add(project)
    await db_session.flush()
    ctx = CommandContext(actor=actor, correlation_id="fp")
    _ = ctx
    first = await canonical_fingerprint(db_session, project.id)
    second = await canonical_fingerprint(db_session, project.id)
    assert first == second


@pytest.mark.persistence
@pytest.mark.asyncio
async def test_fingerprint_changes_when_cycle_added(db_session: AsyncSession) -> None:
    from core.domain.delivery_cycles.service import DeliveryCycleService
    from core.domain.enums import DeliveryCycleType

    actor = await ensure_system_actor(db_session)
    project = Project(key=f"FP2-{uuid.uuid4().hex[:6]}", name="fp2")
    db_session.add(project)
    await db_session.flush()
    ctx = CommandContext(actor=actor, correlation_id="fp2")
    before = await canonical_fingerprint(db_session, project.id)
    await DeliveryCycleService().create(
        db_session,
        project.id,
        DeliveryCycleType.GREENFIELD_BUILD,
        "cycle",
        ctx,
    )
    after = await canonical_fingerprint(db_session, project.id)
    assert before != after
