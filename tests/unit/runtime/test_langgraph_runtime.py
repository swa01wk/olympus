from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from core.runtime.contracts import AgentResumeRequest, AgentRunRequest, ContextItem
from core.runtime.langgraph_runtime import LangGraphRuntime
from core.runtime.providers.fake_provider import FakeProvider, FakeScriptStep

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_langgraph_diagnostic_run(
    model_router, fake_provider: FakeProvider, db_session
) -> None:
    text = Path("tests/fixtures/diagnostic/paragraph.txt").read_text(encoding="utf-8")
    fake_provider.set_script(
        [
            FakeScriptStep(
                structured={
                    "title": "Olympus routing",
                    "bullet_points": ["Audited path", "Schema validation"],
                    "word_count_estimate": 40,
                }
            )
        ]
    )
    runtime = LangGraphRuntime(db_session, model_router)
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
    assert result.model_call_ids


@pytest.mark.asyncio
async def test_resume_from_continuation_without_checkpoint(
    model_router, fake_provider: FakeProvider, db_session
) -> None:
    text = Path("tests/fixtures/diagnostic/paragraph.txt").read_text(encoding="utf-8")
    fake_provider.set_script(
        [
            FakeScriptStep(
                structured={
                    "title": "Resume ok",
                    "bullet_points": ["one"],
                    "word_count_estimate": 10,
                }
            )
        ]
    )
    runtime = LangGraphRuntime(db_session, model_router)
    run_id = uuid.uuid4()
    result = await runtime.resume(
        AgentResumeRequest(
            run_id=run_id,
            agent_profile="diagnostic.structured_echo",
            continuation={"source_text": text},
        )
    )
    assert result.status == "OUTPUT_PRODUCED"
