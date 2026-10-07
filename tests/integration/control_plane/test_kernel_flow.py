from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_greenfield_cycle_and_fail_closed_guard(api_client) -> None:
    project = await api_client.post(
        "/projects",
        json={"key": "demo", "name": "Demo"},
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]
    cycle = await api_client.post(
        f"/projects/{project_id}/delivery-cycles",
        json={"type": "GREENFIELD_BUILD", "objective": "Build"},
    )
    assert cycle.status_code == 201, cycle.text
    body = cycle.json()
    assert body["state"] == "DISCOVERY"
    cycle_id = body["id"]
    cmd = await api_client.post(
        f"/delivery-cycles/{cycle_id}/commands/start_product_modeling",
        json={"expected_state": "DISCOVERY"},
    )
    assert cmd.status_code == 422
    assert "NO_PRODUCT_SOURCE" in cmd.text
