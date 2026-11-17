from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from core.autopilot.models import AutopilotState
from core.domain.enums import TaskStatus
from core.domain.tasks.models import Task
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from tests.workflow.product_model.conftest import control_app, operator_token  # noqa: F401

_OPEN = [
    TaskStatus.DRAFT,
    TaskStatus.BLOCKED,
    TaskStatus.READY,
    TaskStatus.QUEUED,
    TaskStatus.RUNNING,
]


@pytest.fixture(autouse=True)
async def _leave_no_runnable_work(async_engine: AsyncEngine) -> AsyncIterator[None]:
    """These tests commit through the API. Later tests admit READY tasks database-wide
    (``AdmissionService.admit_batch``), so cancel whatever Autopilot started and turn it off."""
    yield
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        cycle_ids = select(AutopilotState.delivery_cycle_id)
        await session.execute(
            update(Task)
            .where(Task.delivery_cycle_id.in_(cycle_ids), Task.status.in_(_OPEN))
            .values(status=TaskStatus.CANCELLED)
        )
        await session.execute(update(AutopilotState).values(enabled=False))
