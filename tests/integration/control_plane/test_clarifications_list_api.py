from __future__ import annotations

import uuid
from uuid import uuid4

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_clarifications_filters_by_project_and_status(api_client, async_engine) -> None:
    from core.domain.enums import ClarificationStatus
    from core.domain.executions.models import Clarification
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    projects: list[tuple[str, str]] = []
    for name in ("Clar A", "Clar B"):
        project = await api_client.post(
            "/projects", json={"key": f"clr-{uuid4().hex[:6]}", "name": name}
        )
        project_id = project.json()["id"]
        cycle = await api_client.post(
            f"/projects/{project_id}/delivery-cycles",
            json={"type": "GREENFIELD_BUILD", "objective": name},
        )
        projects.append((project_id, cycle.json()["id"]))

    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        for idx, (project_id, cycle_id) in enumerate(projects):
            for status in (ClarificationStatus.OPEN, ClarificationStatus.ANSWERED):
                session.add(
                    Clarification(
                        key=f"CL-{idx}-{status.value}",
                        project_id=uuid.UUID(project_id),
                        delivery_cycle_id=uuid.UUID(cycle_id),
                        question=f"{idx} {status.value}?",
                        status=status,
                    )
                )

    project_a = projects[0][0]
    scoped = await api_client.get(
        "/clarifications", params={"project_id": project_a, "status": "OPEN"}
    )
    assert scoped.status_code == 200, scoped.text
    assert [c["key"] for c in scoped.json()] == ["CL-0-OPEN"]

    all_for_a = await api_client.get("/clarifications", params={"project_id": project_a})
    assert sorted(c["key"] for c in all_for_a.json()) == ["CL-0-ANSWERED", "CL-0-OPEN"]

    unscoped = await api_client.get("/clarifications", params={"status": "OPEN"})
    unscoped_keys = {c["key"] for c in unscoped.json()}
    assert {"CL-0-OPEN", "CL-1-OPEN"} <= unscoped_keys
