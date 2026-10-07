from __future__ import annotations

import uuid

import pytest
from core.domain.model_calls.models import ModelCall
from core.runtime.budget import get_budget_ledger
from core.runtime.contracts import ContextItem, ModelRequest
from core.runtime.errors import BudgetExceeded, ProviderAuthError, SchemaValidationFailed
from core.runtime.profiles.diagnostic import DiagnosticSummary
from core.runtime.providers.fake_provider import (
    FakeProvider,
    FakeScriptStep,
    fake_auth_error,
    fake_rate_limit,
)
from sqlalchemy import select

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_schema_retry_then_success(model_router, fake_provider: FakeProvider) -> None:
    fake_provider.set_script(
        [
            FakeScriptStep(
                structured={"title": "bad", "bullet_points": [], "word_count_estimate": 1}
            ),
            FakeScriptStep(
                structured={
                    "title": "ok",
                    "bullet_points": ["one"],
                    "word_count_estimate": 12,
                }
            ),
        ]
    )
    result = await model_router.invoke(
        ModelRequest(
            purpose="test",
            alias="verification_planning",
            system_instructions="Return JSON",
            context=[ContextItem(kind="TEXT", content="hello world")],
            output_schema=DiagnosticSummary,
            metadata={"agent_profile": "test", "correlation_id": "c1"},
        )
    )
    assert result.parsed_output is not None
    row = await model_router._session.get(ModelCall, result.model_call_id)
    assert row is not None
    assert row.schema_retries == 1
    assert row.status == "SUCCEEDED"


@pytest.mark.asyncio
async def test_schema_exhausted_raises(model_router, fake_provider: FakeProvider) -> None:
    fake_provider.set_script(
        [
            FakeScriptStep(
                structured={"title": "bad", "bullet_points": [], "word_count_estimate": 1}
            ),
            FakeScriptStep(
                structured={"title": "bad", "bullet_points": [], "word_count_estimate": 1}
            ),
            FakeScriptStep(
                structured={"title": "bad", "bullet_points": [], "word_count_estimate": 1}
            ),
        ]
    )
    with pytest.raises(SchemaValidationFailed):
        await model_router.invoke(
            ModelRequest(
                purpose="test",
                alias="verification_planning",
                system_instructions="Return JSON",
                context=[ContextItem(kind="TEXT", content="hello")],
                output_schema=DiagnosticSummary,
                metadata={"agent_profile": "test", "correlation_id": "c2"},
            )
        )
    rows = (
        (
            await model_router._session.execute(
                select(ModelCall).where(ModelCall.correlation_id == "c2")
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].status == "FAILED_SCHEMA"
    assert rows[0].validation_errors


@pytest.mark.asyncio
async def test_rate_limit_retried(model_router, fake_provider: FakeProvider) -> None:
    fake_provider.set_script(
        [
            FakeScriptStep(error=fake_rate_limit(0.01)),
            FakeScriptStep(
                structured={"title": "ok", "bullet_points": ["a"], "word_count_estimate": 2}
            ),
        ]
    )
    result = await model_router.invoke(
        ModelRequest(
            purpose="test",
            alias="verification_planning",
            system_instructions="Return JSON",
            context=[ContextItem(kind="TEXT", content="x")],
            output_schema=DiagnosticSummary,
            metadata={"agent_profile": "test", "correlation_id": "c3"},
        )
    )
    assert result.parsed_output is not None
    row = await model_router._session.get(ModelCall, result.model_call_id)
    assert row is not None
    assert row.transport_retries >= 1


@pytest.mark.asyncio
async def test_auth_error_not_retried(model_router, fake_provider: FakeProvider) -> None:
    fake_provider.set_script([FakeScriptStep(error=fake_auth_error())])
    with pytest.raises(ProviderAuthError):
        await model_router.invoke(
            ModelRequest(
                purpose="test",
                alias="verification_planning",
                system_instructions="x",
                context=[ContextItem(kind="TEXT", content="x")],
                output_schema=DiagnosticSummary,
                metadata={"agent_profile": "test", "correlation_id": "c4"},
            )
        )


@pytest.mark.asyncio
async def test_budget_blocks_before_provider(
    db_session, system_actor, fake_provider: FakeProvider
) -> None:
    from core.runtime.model_router import ModelRouter

    ledger = get_budget_ledger()
    ledger.reset_session()
    run_id = uuid.uuid4()
    ledger.set_limit(str(run_id), 0.000001)
    router = ModelRouter(
        db_session,
        actor_id=system_actor.id,
        providers={"anthropic": fake_provider},
        budget=ledger,
    )
    fake_provider.set_script(
        [
            FakeScriptStep(
                structured={"title": "ok", "bullet_points": ["a"], "word_count_estimate": 2},
                input_tokens=100_000,
                output_tokens=100_000,
            )
        ]
    )
    with pytest.raises(BudgetExceeded):
        await router.invoke(
            ModelRequest(
                purpose="test",
                alias="verification_planning",
                system_instructions="x",
                context=[ContextItem(kind="TEXT", content="x" * 5000)],
                output_schema=DiagnosticSummary,
                metadata={
                    "agent_profile": "test",
                    "correlation_id": "c5",
                    "execution_id": str(run_id),
                    "budget_usd": "0.000001",
                },
            )
        )


@pytest.mark.asyncio
async def test_fake_provider_blocked_outside_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLYMPUS_ENV", "journey")
    monkeypatch.setenv("LLM_LIVE_TESTS", "1")
    from core.config.settings import clear_settings_cache

    clear_settings_cache()
    with pytest.raises(RuntimeError, match="FakeProvider"):
        FakeProvider()
