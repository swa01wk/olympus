from __future__ import annotations

import pytest
from apps.control_api.main import create_app
from core.config.settings import OlympusSettings
from core.db.engine import dispose_engine
from core.domain.actors.models import Actor, ApiToken
from core.domain.actors.tokens import generate_token, hash_token
from core.domain.enums import ActorKind, ActorRole
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.release_harness import ready_eligible_release

pytestmark = pytest.mark.security


@pytest.mark.asyncio
async def test_agent_token_cannot_approve_release(
    async_engine,
    postgres_url,
    tmp_path,
    system_ctx,
) -> None:
    from core.commands.context import CommandContext

    agent_token = generate_token()
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    release_id = None
    async with factory() as session, session.begin():
        operator = Actor(
            kind=ActorKind.HUMAN,
            name="sec-release-operator",
            roles=[ActorRole.OPERATOR.value, ActorRole.APPROVER.value],
        )
        session.add(operator)
        await session.flush()
        system = Actor(
            kind=ActorKind.SYSTEM,
            name="sec-release-sys",
            roles=[ActorRole.SYSTEM.value],
        )
        session.add(system)
        await session.flush()
        op_ctx = CommandContext(actor=operator, correlation_id="sec-rel-op")
        sys_ctx = CommandContext(actor=system, correlation_id="sec-rel-sys")
        _, _, release = await ready_eligible_release(
            session, sys_ctx, op_ctx, project_key="sec-rel"
        )
        release_id = release.id
        agent = Actor(
            kind=ActorKind.AGENT,
            name="forge-agent",
            roles=[ActorRole.SYSTEM.value],
        )
        session.add(agent)
        await session.flush()
        session.add(ApiToken(actor_id=agent.id, token_hash=hash_token(agent_token)))
    assert release_id is not None
    await dispose_engine()
    settings = OlympusSettings(
        database_url=postgres_url,
        olympus_workspace_root=tmp_path / "ws",
        olympus_storage_root=tmp_path / "storage",
        olympus_env="test",
    )
    app = create_app(settings=settings)
    app.state.session_factory = factory
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {agent_token}"},
    ) as client:
        resp = await client.post(f"/releases/{release_id}/approve")
    assert resp.status_code == 403
