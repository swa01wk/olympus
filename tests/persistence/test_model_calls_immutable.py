from __future__ import annotations

import pytest
from core.domain.model_calls.models import ModelCall
from sqlalchemy import text

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_model_calls_row_immutable(db_session) -> None:
    row = ModelCall(
        agent_profile="test",
        purpose="p",
        alias="verification_planning",
        provider="anthropic",
        model="claude-test",
        prompt_hash="abc",
        status="SUCCEEDED",
        correlation_id="corr",
    )
    db_session.add(row)
    await db_session.flush()
    with pytest.raises(Exception, match="mutation forbidden|forbidden"):
        await db_session.execute(
            text("UPDATE model_calls SET status = 'FAILED' WHERE id = :id"),
            {"id": row.id},
        )
        await db_session.flush()
