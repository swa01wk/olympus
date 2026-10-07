from __future__ import annotations

import uuid

import pytest
from core.runtime.contracts import AgentRunRequest, ContextItem
from core.runtime.langgraph_runtime import LangGraphRuntime
from core.runtime.providers.fake_provider import FakeProvider, FakeScriptStep

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_ask_question_ambiguous_checkpoints(
    model_router, fake_provider: FakeProvider, db_session
) -> None:
    runtime = LangGraphRuntime(db_session, model_router)
    run_id = uuid.uuid4()
    result = await runtime.run(
        AgentRunRequest(
            run_id=run_id,
            agent_profile="diagnostic.ask_question",
            context=[
                ContextItem(
                    kind="TEXT",
                    content="[[AMBIGUOUS]] please clarify",
                    provenance="DETERMINISTIC",
                )
            ],
        )
    )
    assert result.status == "CHECKPOINT_REQUESTED"
    assert result.checkpoint_request is not None
    assert result.checkpoint_request.questions


@pytest.mark.asyncio
async def test_ask_question_clear_path_uses_llm(
    model_router, fake_provider: FakeProvider, db_session
) -> None:
    fake_provider.set_script(
        [
            FakeScriptStep(
                structured={
                    "title": "Ok",
                    "bullet_points": ["a"],
                    "word_count_estimate": 1,
                }
            )
        ]
    )
    runtime = LangGraphRuntime(db_session, model_router)
    result = await runtime.run(
        AgentRunRequest(
            run_id=uuid.uuid4(),
            agent_profile="diagnostic.ask_question",
            context=[ContextItem(kind="TEXT", content="clear text", provenance="DETERMINISTIC")],
        )
    )
    assert result.status == "OUTPUT_PRODUCED"
