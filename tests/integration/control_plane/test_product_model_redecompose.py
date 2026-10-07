from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_clarification_answer_triggers_redecompose_task(api_client, async_engine) -> None:
    from core.domain.tasks.models import Task
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    rkey = f"rd-{uuid4().hex[:6]}"
    project = await api_client.post("/projects", json={"key": rkey, "name": "RD"})
    project_id = project.json()["id"]
    cycle = await api_client.post(
        f"/projects/{project_id}/delivery-cycles",
        json={"type": "GREENFIELD_BUILD", "objective": "rd"},
    )
    cycle_id = cycle.json()["id"]
    prd = Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "PRD.md"
    up = await api_client.post(
        f"/projects/{project_id}/sources",
        params={"delivery_cycle_id": cycle_id},
        files={"file": ("PRD.md", prd.read_bytes(), "text/markdown")},
        headers={"Idempotency-Key": f"rd-{uuid4().hex[:8]}"},
    )
    assert up.status_code == 200
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    clarification_id: str
    async with factory() as session, session.begin():
        from core.domain.enums import ClarificationStatus
        from core.domain.executions.models import Clarification
        from core.domain.sequences import next_project_key

        cl_key = await next_project_key(session, project_id, "clarification", prefix="CL")
        cl = Clarification(
            key=cl_key,
            project_id=project_id,
            delivery_cycle_id=cycle_id,
            question="What about closed tickets?",
            context={"text": "ambiguous"},
            options=[],
            blocking=True,
            status=ClarificationStatus.OPEN,
        )
        session.add(cl)
        await session.flush()
        clarification_id = str(cl.id)

    async with factory() as session:
        count_before = (
            await session.execute(
                select(func.count()).select_from(Task).where(Task.delivery_cycle_id == cycle_id)
            )
        ).scalar_one()

    answer = await api_client.post(
        f"/clarifications/{clarification_id}/answer",
        json={"answer": "Closed tickets return HTTP 409"},
    )
    assert answer.status_code == 200, answer.text
    assert "redecompose_task_id" in answer.json()

    async with factory() as session:
        count_after = (
            await session.execute(
                select(func.count()).select_from(Task).where(Task.delivery_cycle_id == cycle_id)
            )
        ).scalar_one()
    assert count_after == count_before + 1
