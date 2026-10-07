from __future__ import annotations

import pytest
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind
from core.security.tokens import actor_can, create_api_token, token_has_scope

pytestmark = pytest.mark.security


def test_admin_scope_implies_all() -> None:
    assert token_has_scope(["admin"], "approve")


@pytest.mark.asyncio
async def test_operate_scope_denied_for_admin_endpoint(db_session) -> None:
    actor = Actor(kind=ActorKind.HUMAN, name="scope-test", roles=["operator"])
    db_session.add(actor)
    await db_session.flush()
    _raw, row = await create_api_token(db_session, actor_id=actor.id, scopes=["read"])
    assert not actor_can("operate", actor, list(row.scopes or []))
