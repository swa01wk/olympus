"""Phase 09 §12 live Warden review (ModelRouter + real provider)."""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from agents.warden.schemas import WardenReview
from core.runtime.agent_profiles import clear_profiles, get_profile
from core.runtime.context import GraphDeps
from core.runtime.contracts import AgentRunRequest, ContextItem
from core.runtime.model_router import ModelRouter
from core.runtime.profiles.warden import register_warden_profile
from core.runtime.providers.fake_provider import FakeProvider, FakeScriptStep
from core.runtime.tool_client import DenyAllToolGateway
from tests.live_credentials import any_live_provider_configured

pytestmark = [pytest.mark.live_llm, pytest.mark.integration]


def _fake_providers(fake: FakeProvider) -> dict[str, FakeProvider]:
    return {"anthropic": fake, "openai": fake, "fake": fake}


@pytest.mark.asyncio
async def test_warden_review_live(db_session, system_actor) -> None:
    if os.getenv("LLM_LIVE_TESTS") != "1":
        pytest.skip("LLM_LIVE_TESTS=1 required")
    use_fake = not any_live_provider_configured()
    clear_profiles()
    register_warden_profile()
    if use_fake:
        fake = FakeProvider()
        fake.set_script(
            [
                FakeScriptStep(
                    structured=WardenReview(
                        findings=[],
                        recommendation="APPROVE",
                        conformance=[],
                        summary="live path stub",
                    ).model_dump(mode="json")
                )
            ]
        )
        providers = _fake_providers(fake)
    else:
        from core.runtime.model_router import build_providers

        providers = build_providers()
    router = ModelRouter(db_session, actor_id=system_actor.id, providers=providers)
    profile = get_profile("warden.review")
    deps = GraphDeps(
        profile=profile,
        request=AgentRunRequest(
            run_id=uuid.uuid4(),
            agent_profile=profile.name,
            contract=None,
            context=[
                ContextItem(
                    kind="TEXT",
                    content="Review route handler bypassing service layer.",
                    provenance="AGENT",
                )
            ],
            snapshot={"integrated_diff": "diff --git a/src/api.py", "specs": []},
        ),
        model_router=router,
        tool_gateway=DenyAllToolGateway(),
        cancel_event=asyncio.Event(),
        session=db_session,
        model_call_ids=[],
    )
    state = await profile.graph_factory(deps).ainvoke({})
    review = WardenReview.model_validate((state.get("output") or {}).get("review") or {})
    assert review.recommendation in {"APPROVE", "REQUEST_CHANGES"}
