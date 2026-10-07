from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from core.runtime.contracts import ContextItem, ModelRequest
from core.runtime.model_router import ModelRouter, build_providers
from core.runtime.profiles.diagnostic import DiagnosticSummary
from tests.live_credentials import openai_configured

pytestmark = [
    pytest.mark.live_llm,
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("LLM_LIVE_TESTS") != "1", reason="LLM_LIVE_TESTS not enabled"),
]


@pytest.mark.asyncio
async def test_live_structured_invoke(db_session, system_actor) -> None:
    from tests.live_credentials import any_live_provider_configured

    if not any_live_provider_configured():
        pytest.skip("No live provider API key configured")

    text = Path("tests/fixtures/diagnostic/paragraph.txt").read_text(encoding="utf-8")
    router = ModelRouter(
        db_session,
        actor_id=system_actor.id,
        providers=build_providers(),
    )
    result = await router.invoke(
        ModelRequest(
            purpose="live.diagnostic",
            alias="verification_planning",
            system_instructions="Summarize the text into the required JSON schema.",
            context=[ContextItem(kind="TEXT", content=text, provenance="DETERMINISTIC")],
            output_schema=DiagnosticSummary,
            metadata={
                "agent_profile": "diagnostic.structured_echo",
                "correlation_id": str(uuid.uuid4()),
            },
        )
    )
    assert isinstance(result.parsed_output, DiagnosticSummary)
    assert 1 <= len(result.parsed_output.bullet_points) <= 5
    if openai_configured():
        assert result.provider == "openai"
        assert result.model == "gpt-5.4-mini"
    assert result.provider_request_id
    assert result.input_tokens > 0
    assert result.cost_usd_estimate > 0
