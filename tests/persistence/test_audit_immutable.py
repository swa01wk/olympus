from __future__ import annotations

import uuid

import pytest
from core.domain.audit.append import append_audit
from core.domain.enums import ActorKind
from sqlalchemy import text

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_audit_delete_forbidden(db_session, system_actor) -> None:
    row = await append_audit(
        db_session,
        actor_id=system_actor.id,
        actor_kind=ActorKind.SYSTEM,
        action="test",
        target_type="t",
        target_id=str(uuid.uuid4()),
        correlation_id="c",
    )
    with pytest.raises(Exception, match="mutation forbidden|forbidden"):
        await db_session.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": row.id})
        await db_session.flush()
