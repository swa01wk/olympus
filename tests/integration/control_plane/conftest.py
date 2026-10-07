from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from apps.control_api.main import create_app
from core.config.settings import OlympusSettings
from core.db.engine import dispose_engine
from core.domain.actors.models import Actor, ApiToken
from core.domain.actors.tokens import generate_token, hash_token
from core.domain.enums import ActorKind, ActorRole
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest.fixture
async def operator_token(async_engine) -> str:
    token = generate_token()
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        actor = Actor(
            kind=ActorKind.HUMAN,
            name=f"test-operator-{uuid4().hex[:8]}",
            roles=[ActorRole.OPERATOR.value, ActorRole.APPROVER.value],
        )
        session.add(actor)
        await session.flush()
        session.add(ApiToken(actor_id=actor.id, token_hash=hash_token(token)))
    return token


@pytest.fixture
async def viewer_token(async_engine) -> str:
    token = generate_token()
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        actor = Actor(
            kind=ActorKind.HUMAN,
            name=f"test-viewer-{uuid4().hex[:8]}",
            roles=[ActorRole.VIEWER.value],
        )
        session.add(actor)
        await session.flush()
        session.add(
            ApiToken(
                actor_id=actor.id,
                token_hash=hash_token(token),
                scopes=["read", "operate", "approve"],
            )
        )
    return token


@pytest.fixture
async def control_app(
    async_engine,
    postgres_url: str,
    tmp_path,
) -> FastAPI:
    await dispose_engine()
    settings = OlympusSettings(
        database_url=postgres_url,
        olympus_workspace_root=tmp_path / "ws",
        olympus_storage_root=tmp_path / "storage",
        olympus_env="test",
    )
    session_factory = async_sessionmaker(
        bind=async_engine, class_=AsyncSession, expire_on_commit=False
    )
    app = create_app(settings=settings)
    app.state.session_factory = session_factory
    return app


@pytest.fixture
async def api_client(
    control_app: FastAPI,
    operator_token: str,
) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=control_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        yield client


@pytest.fixture
async def agent_token(async_engine) -> str:
    token = generate_token()
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session, session.begin():
        actor = Actor(
            kind=ActorKind.AGENT,
            name=f"test-agent-{uuid4().hex[:8]}",
            roles=[ActorRole.OPERATOR.value],
        )
        session.add(actor)
        await session.flush()
        session.add(ApiToken(actor_id=actor.id, token_hash=hash_token(token)))
    return token


@pytest.fixture
async def agent_client(control_app: FastAPI, agent_token: str) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=control_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {agent_token}"},
    ) as client:
        yield client


@pytest.fixture
async def viewer_client(control_app: FastAPI, viewer_token: str) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=control_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {viewer_token}"},
    ) as client:
        yield client
