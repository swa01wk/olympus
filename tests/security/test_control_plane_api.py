from __future__ import annotations

import pytest
from apps.control_api.main import create_app
from core.config.settings import OlympusSettings
from core.db.engine import dispose_engine
from core.domain.actors.models import ApiToken
from core.domain.actors.tokens import generate_token, hash_token
from core.domain.enums import ActorKind, ActorRole
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.security


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(async_engine, postgres_url, tmp_path) -> None:
    await dispose_engine()
    settings = OlympusSettings(
        database_url=postgres_url,
        olympus_workspace_root=tmp_path / "ws",
        olympus_storage_root=tmp_path / "storage",
        olympus_env="test",
    )
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    app = create_app(settings=settings)
    app.state.session_factory = factory
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/projects", json={"key": "x", "name": "X"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_revoked_token_returns_401(async_engine, postgres_url, tmp_path) -> None:
    from datetime import UTC, datetime

    from core.domain.actors.models import Actor

    token = generate_token()
    await dispose_engine()
    settings = OlympusSettings(
        database_url=postgres_url,
        olympus_workspace_root=tmp_path / "ws",
        olympus_storage_root=tmp_path / "storage",
        olympus_env="test",
    )
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        actor = Actor(
            kind=ActorKind.HUMAN,
            name=f"revoked-{generate_token()[:8]}",
            roles=[ActorRole.VIEWER.value],
        )
        session.add(actor)
        await session.flush()
        session.add(
            ApiToken(
                actor_id=actor.id,
                token_hash=hash_token(token),
                revoked_at=datetime.now(UTC),
            )
        )
    app = create_app(settings=settings)
    app.state.session_factory = factory
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        resp = await client.post("/projects", json={"key": "x", "name": "X"})
    assert resp.status_code == 401


def test_openapi_request_bodies_forbid_state_and_status() -> None:
    app = create_app(
        settings=OlympusSettings(
            database_url="postgresql+asyncpg://unused",
            olympus_workspace_root="/tmp/ws",
            olympus_storage_root="/tmp/storage",
            olympus_env="test",
        )
    )
    schema = app.openapi()

    paths = schema.get("paths", {})
    assert isinstance(paths, dict)
    for route, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method, spec in methods.items():
            if method not in {"post", "put", "patch"}:
                continue
            body = spec.get("requestBody", {})
            content = body.get("content", {}) if isinstance(body, dict) else {}
            json_schema = content.get("application/json", {}).get("schema", {})
            props = json_schema.get("properties", {})
            if isinstance(props, dict):
                for forbidden in ("state", "status"):
                    assert forbidden not in props, (
                        f"{method.upper()} {route} request body exposes {forbidden}"
                    )
