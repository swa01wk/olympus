"""Fault proxy behavior (in-process ASGI; compose service uses same module)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from tests.support.fault_proxy import app

pytestmark = pytest.mark.connector


@pytest.mark.asyncio
async def test_fault_proxy_status_5xx() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://fault") as client:
        resp = await client.get(
            "/anything",
            headers={
                "X-Olympus-Fault": "status_5xx",
                "X-Olympus-Target": "http://example.com",
            },
        )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_fault_proxy_requires_target() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://fault") as client:
        resp = await client.get("/x")
    assert resp.status_code == 400
