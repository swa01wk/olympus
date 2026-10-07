from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from core.runtime.contracts import AgentRunRequest, ContextItem
from core.runtime.langgraph_runtime import LangGraphRuntime
from core.runtime.model_router import ModelRouter, build_providers
from tests.live_credentials import any_live_provider_configured

pytestmark = [
    pytest.mark.live_llm,
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("LLM_LIVE_TESTS") != "1", reason="LLM_LIVE_TESTS not enabled"),
]


@pytest.mark.asyncio
async def test_langgraph_diagnostic_live(db_session, system_actor) -> None:
    if not any_live_provider_configured():
        pytest.skip("No live provider API key configured")

    text = Path("tests/fixtures/diagnostic/paragraph.txt").read_text(encoding="utf-8")
    router = ModelRouter(
        db_session,
        actor_id=system_actor.id,
        providers=build_providers(),
    )
    runtime = LangGraphRuntime(db_session, router)
    run_id = uuid.uuid4()
    result = await runtime.run(
        AgentRunRequest(
            run_id=run_id,
            agent_profile="diagnostic.structured_echo",
            context=[ContextItem(kind="TEXT", content=text, provenance="DETERMINISTIC")],
        )
    )
    assert result.status == "OUTPUT_PRODUCED"
    assert result.output is not None
    events = [event async for event in runtime.stream(str(run_id))]
    assert any(e.type == "OUTPUT_PROPOSED" for e in events)
