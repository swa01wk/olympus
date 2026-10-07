from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_orchestrator_session_create_and_get(api_client: AsyncClient) -> None:
    project = await api_client.post(
        "/projects",
        json={"name": "Orch Session", "key": f"OS{uuid.uuid4().hex[:6].upper()}"},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert project.status_code == 201
    project_id = project.json()["id"]
    cycle = await api_client.post(
        f"/projects/{project_id}/delivery-cycles",
        json={"type": "GREENFIELD_BUILD", "objective": "orch session"},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert cycle.status_code == 201
    cycle_id = cycle.json()["id"]

    created = await api_client.post(
        "/orchestrator/sessions",
        json={"project_id": project_id, "delivery_cycle_id": cycle_id},
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["id"]
    assert created.json()["expires_at"]

    got = await api_client.get(f"/orchestrator/sessions/{session_id}")
    assert got.status_code == 200, got.text
    assert got.json()["id"] == session_id
    assert got.json()["delivery_cycle_id"] == cycle_id

    turn = await api_client.post(
        f"/orchestrator/sessions/{session_id}/turns",
        json={"message": "what is the cycle status?"},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert turn.status_code == 200, turn.text
    assert turn.json()["execution_id"]
