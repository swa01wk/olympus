from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from apps.control_api.main import create_app
from core.config.settings import OlympusSettings
from core.observability.correlation import CORRELATION_HEADER
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@asynccontextmanager
async def _client_for(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.mark.integration
async def test_health_ok() -> None:
    app = create_app()
    async with _client_for(app) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert CORRELATION_HEADER in response.headers


@pytest.mark.integration
async def test_ready_ok_with_db(tmp_path: Path, postgres_url: str, migrated_db: str) -> None:
    assert migrated_db == postgres_url
    settings = OlympusSettings(
        database_url=postgres_url,
        olympus_workspace_root=tmp_path / "ws",
        olympus_storage_root=tmp_path / "storage",
        olympus_env="test",
    )
    app = create_app(settings=settings)
    async with _client_for(app) as client:
        response = await client.get("/ready")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["db"] == "ok"
    assert body["migrations"] == "head"
    assert body.get("storage") == "ok"
    assert body.get("sandbox") == "ok"


@pytest.mark.integration
async def test_ready_503_bad_db(tmp_path: Path) -> None:
    settings = OlympusSettings(
        database_url="postgresql+psycopg://invalid:invalid@127.0.0.1:1/nope",
        olympus_workspace_root=tmp_path / "ws",
        olympus_storage_root=tmp_path / "storage",
        olympus_env="test",
    )
    app = create_app(settings=settings)
    async with _client_for(app) as client:
        response = await client.get("/ready")
    assert response.status_code == 503


@pytest.mark.integration
async def test_correlation_header_echo_and_generation(
    tmp_path: Path, postgres_url: str, migrated_db: str
) -> None:
    assert migrated_db == postgres_url
    settings = OlympusSettings(
        database_url=postgres_url,
        olympus_workspace_root=tmp_path / "ws",
        olympus_storage_root=tmp_path / "storage",
        olympus_env="test",
    )
    app = create_app(settings=settings)
    correlation = "550e8400-e29b-41d4-a716-446655440000"
    async with _client_for(app) as client:
        echoed = await client.get("/health", headers={CORRELATION_HEADER: correlation})
        generated = await client.get("/health")
    assert echoed.headers[CORRELATION_HEADER] == correlation
    assert CORRELATION_HEADER in generated.headers
    assert generated.headers[CORRELATION_HEADER] != ""
