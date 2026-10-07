from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_command_catalog(api_client: AsyncClient) -> None:
    res = await api_client.get("/commands/catalog")
    assert res.status_code == 200
    body = res.json()
    assert body["registered_count"] >= 10
    assert any(c["command"] == "create_project" for c in body["commands"])


@pytest.mark.asyncio
async def test_inbox_and_overviews_empty_project(api_client: AsyncClient) -> None:
    create = await api_client.post(
        "/projects",
        json={"name": "View Test", "key": f"VW{uuid.uuid4().hex[:6].upper()}"},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert create.status_code == 201
    project_id = create.json()["id"]
    overview = await api_client.get(f"/views/projects/{project_id}/overview")
    assert overview.status_code == 200
    inbox = await api_client.get("/views/inbox")
    assert inbox.status_code == 200
    assert isinstance(inbox.json(), list)

    inbox_project = await api_client.get(
        "/views/inbox",
        params={"project_id": project_id},
    )
    assert inbox_project.status_code == 200
    assert isinstance(inbox_project.json(), list)

    coverage = await api_client.get(f"/views/projects/{project_id}/coverage")
    assert coverage.status_code == 200

    cycle = await api_client.post(
        f"/projects/{project_id}/delivery-cycles",
        json={"type": "GREENFIELD_BUILD", "objective": "views"},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert cycle.status_code == 201
    cycle_id = cycle.json()["id"]

    inbox_cycle = await api_client.get(
        "/views/inbox",
        params={"delivery_cycle_id": cycle_id},
    )
    assert inbox_cycle.status_code == 200
    assert isinstance(inbox_cycle.json(), list)

    cp = await api_client.get(f"/views/delivery-cycles/{cycle_id}/control-plane")
    assert cp.status_code == 200
    assert cp.json()["delivery_cycle_id"] == cycle_id

    agent = await api_client.get(f"/views/projects/{project_id}/agent-activity")
    assert agent.status_code == 200
    assert agent.json()["project_id"] == project_id

    dag = await api_client.get(f"/views/tasks/{cycle_id}/dag")
    assert dag.status_code == 200

    preview_before = await api_client.get(f"/delivery-cycles/{cycle_id}/next-transitions")
    assert preview_before.status_code == 200
    overview2 = await api_client.get(f"/views/delivery-cycles/{cycle_id}/overview")
    assert overview2.status_code == 200
    preview_after = await api_client.get(f"/delivery-cycles/{cycle_id}/next-transitions")
    assert preview_after.json() == preview_before.json()
