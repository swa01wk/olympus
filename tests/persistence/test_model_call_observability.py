from __future__ import annotations

import pytest
from core.domain.model_calls.models import ModelCall
from core.runtime.contracts import ContextItem, ModelRequest
from core.runtime.model_router import ModelRouter
from core.runtime.providers.fake_provider import FakeProvider, FakeScriptStep
from sqlalchemy import select

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_model_router_persists_call_metadata(db_session, system_actor) -> None:
    fake = FakeProvider()
    fake.set_script(
        [
            FakeScriptStep(
                structured={"title": "t", "bullet_points": ["a"], "word_count_estimate": 3}
            )
        ]
    )
    router = ModelRouter(
        db_session,
        actor_id=system_actor.id,
        providers={"anthropic": fake, "openai": fake},
    )
    await router.invoke(
        ModelRequest(
            alias="planning",
            purpose="unit-meta",
            system_instructions="sys",
            context=[ContextItem(kind="TEXT", content="hello")],
            output_schema=None,
            metadata={"agent_profile": "test.profile", "correlation_id": "meta-1"},
        )
    )
    result = await db_session.execute(select(ModelCall).where(ModelCall.correlation_id == "meta-1"))
    row = result.scalar_one()
    assert row.provider in {"fake", "openai", "anthropic"}
    assert row.alias == "planning"
    assert row.input_tokens >= 0
    assert row.latency_ms >= 0
