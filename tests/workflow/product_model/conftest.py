"""Control-plane HTTP fixtures for product-model workflow tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from apps.control_api.main import create_app
from core.config.settings import OlympusSettings
from core.db.engine import dispose_engine
from core.domain.actors.models import Actor, ApiToken
from core.domain.actors.tokens import generate_token, hash_token
from core.domain.enums import ActorKind, ActorRole
from fastapi import FastAPI
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
