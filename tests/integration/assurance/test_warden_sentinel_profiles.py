"""Warden/Sentinel profiles through ModelRouter (FakeProvider)."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from agents.sentinel.schemas import CharacterizationPlan, VerificationPlan
from agents.warden.schemas import WardenReview
from core.runtime.agent_profiles import clear_profiles, get_profile
from core.runtime.context import GraphDeps
from core.runtime.contracts import AgentRunRequest, ContextItem
from core.runtime.model_router import ModelRouter
from core.runtime.profiles.sentinel import register_sentinel_profiles
from core.runtime.profiles.warden import register_warden_profile
from core.runtime.providers.fake_provider import FakeProvider, FakeScriptStep
from core.runtime.tool_client import DenyAllToolGateway

pytestmark = pytest.mark.integration


def _fake_providers(fake: FakeProvider) -> dict[str, FakeProvider]:
    return {"anthropic": fake, "openai": fake, "fake": fake}


@pytest.mark.asyncio
async def test_sentinel_plan_via_model_router(db_session, system_actor) -> None:
    clear_profiles()
    register_sentinel_profiles()
    fake = FakeProvider()
    plan_payload = VerificationPlan(checks=[], uncovered_obligations=[], notes=[]).model_dump(
        mode="json"
    )
    fake.set_script([FakeScriptStep(structured=plan_payload)])
    router = ModelRouter(db_session, actor_id=system_actor.id, providers=_fake_providers(fake))
    profile = get_profile("sentinel.plan")
    deps = GraphDeps(
        profile=profile,
        request=AgentRunRequest(
            run_id=uuid.uuid4(),
            agent_profile=profile.name,
            contract=None,
            context=[ContextItem(kind="TEXT", content="plan", provenance="AGENT")],
            snapshot={"obligations": [], "tests": []},
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


@pytest.mark.asyncio
async def test_sentinel_characterize_via_model_router(db_session, system_actor) -> None:
    clear_profiles()
    register_sentinel_profiles()
    fake = FakeProvider()
    plan_payload = CharacterizationPlan(checks=[], skipped=[]).model_dump(mode="json")
    fake.set_script([FakeScriptStep(structured=plan_payload)])
    router = ModelRouter(db_session, actor_id=system_actor.id, providers=_fake_providers(fake))
    profile = get_profile("sentinel.characterize")
    deps = GraphDeps(
        profile=profile,
        request=AgentRunRequest(
            run_id=uuid.uuid4(),
            agent_profile=profile.name,
            contract=None,
            context=[ContextItem(kind="TEXT", content="characterize", provenance="AGENT")],
            snapshot={"acs": [], "behaviors": [], "index_summary": "[]", "code_excerpt": ""},
        ),
        model_router=router,
        tool_gateway=DenyAllToolGateway(),
        cancel_event=asyncio.Event(),
        session=db_session,
        model_call_ids=[],
    )
    state = await profile.graph_factory(deps).ainvoke({})
    plan = CharacterizationPlan.model_validate(state.get("output") or {"checks": [], "skipped": []})
    assert plan.checks is not None


@pytest.mark.asyncio
async def test_warden_review_via_model_router(db_session, system_actor) -> None:
    clear_profiles()
    register_warden_profile()
    fake = FakeProvider()
    fake.set_script(
        [
            FakeScriptStep(
                structured=WardenReview(
                    findings=[],
                    recommendation="APPROVE",
                    conformance=[],
                    summary="ok",
                ).model_dump(mode="json")
            )
        ]
    )
    router = ModelRouter(db_session, actor_id=system_actor.id, providers=_fake_providers(fake))
    profile = get_profile("warden.review")
    deps = GraphDeps(
        profile=profile,
        request=AgentRunRequest(
            run_id=uuid.uuid4(),
            agent_profile=profile.name,
            contract=None,
            context=[ContextItem(kind="TEXT", content="review", provenance="AGENT")],
            snapshot={"integrated_diff": "", "specs": []},
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
