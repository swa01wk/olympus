"""Phase 09 §12 live Sentinel plan (ModelRouter + provider)."""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from agents.sentinel.schemas import VerificationPlan
from core.runtime.agent_profiles import clear_profiles, get_profile
from core.runtime.context import GraphDeps
from core.runtime.contracts import AgentRunRequest, ContextItem
from core.runtime.model_router import ModelRouter, build_providers
from core.runtime.profiles.sentinel import register_sentinel_profiles
from core.runtime.providers.fake_provider import FakeProvider, FakeScriptStep
from core.runtime.tool_client import DenyAllToolGateway
from tests.live_credentials import any_live_provider_configured

pytestmark = [pytest.mark.live_llm, pytest.mark.integration]


def _fake_providers(fake: FakeProvider) -> dict[str, FakeProvider]:
    return {"anthropic": fake, "openai": fake, "fake": fake}


@pytest.mark.asyncio
async def test_sentinel_plan_live(db_session, system_actor) -> None:
    if os.getenv("LLM_LIVE_TESTS") != "1":
        pytest.skip("LLM_LIVE_TESTS=1 required")
    clear_profiles()
    register_sentinel_profiles()
    if any_live_provider_configured():
        providers = build_providers()
    else:
        fake = FakeProvider()
        plan_payload = VerificationPlan(
            checks=[], uncovered_obligations=[], notes=["live path stub"]
        ).model_dump(mode="json")
        fake.set_script([FakeScriptStep(structured=plan_payload)])
        providers = _fake_providers(fake)
    router = ModelRouter(db_session, actor_id=system_actor.id, providers=providers)
    profile = get_profile("sentinel.plan")
    deps = GraphDeps(
        profile=profile,
        request=AgentRunRequest(
            run_id=uuid.uuid4(),
            agent_profile=profile.name,
            contract=None,
            context=[ContextItem(kind="TEXT", content="Plan checks for ACs.", provenance="AGENT")],
            snapshot={"obligations": [{"subject_key": "AC-1"}], "tests": []},
        ),
        model_router=router,
        tool_gateway=DenyAllToolGateway(),
        cancel_event=asyncio.Event(),
        session=db_session,
        model_call_ids=[],
    )
    state = await profile.graph_factory(deps).ainvoke({})
    plan = VerificationPlan.model_validate(
        (state.get("output") or {}).get("verification_plan") or {"checks": []}
    )
    assert plan.checks is not None
