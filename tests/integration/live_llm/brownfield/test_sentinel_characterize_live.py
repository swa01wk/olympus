"""Phase 12 §12 — live sentinel.characterize on supportdesk_r1 (policy-safe)."""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from agents.sentinel.schemas import CharacterizationPlan
from core.runtime.agent_profiles import clear_profiles, get_profile
from core.runtime.context import GraphDeps
from core.runtime.contracts import AgentRunRequest, ContextItem
from core.runtime.model_router import ModelRouter, build_providers
from core.runtime.profiles.sentinel import register_sentinel_profiles
from core.runtime.tool_client import DenyAllToolGateway
from tests.live_credentials import any_live_provider_configured

pytestmark = [pytest.mark.live_llm, pytest.mark.integration]


@pytest.mark.asyncio
async def test_sentinel_characterize_live_supportdesk(db_session, system_actor) -> None:
    if os.environ.get("LLM_LIVE_TESTS") != "1":
        pytest.skip("Set LLM_LIVE_TESTS=1 for live characterize")
    if not any_live_provider_configured():
        pytest.skip("No live provider API key configured")

    os.environ.setdefault(
        "MODEL_REPOSITORY_REASONING",
        os.environ.get("MODEL_DEFAULT", ""),
    )
    from core.config.settings import clear_settings_cache
    from core.runtime.model_policy import clear_models_config_cache

    clear_settings_cache()
    clear_models_config_cache()

    clear_profiles()
    register_sentinel_profiles()
    router = ModelRouter(
        db_session,
        actor_id=system_actor.id,
        providers=build_providers(),
    )
    profile = get_profile("sentinel.characterize")
    deps = GraphDeps(
        profile=profile,
        request=AgentRunRequest(
            run_id=uuid.uuid4(),
            agent_profile=profile.name,
            contract=None,
            context=[
                ContextItem(
                    kind="TEXT",
                    content="Characterize POST /tickets behavior; skip /escalate.",
                    provenance="AGENT",
                )
            ],
            snapshot={
                "acs": [{"ref": "AC-1", "statement": "Create ticket returns 201"}],
                "behaviors": [{"key": "BEH-1", "description": "POST /tickets"}],
                "index_summary": "tests/test_tickets_api.py",
                "code_excerpt": "def test_create_ticket(): ...",
            },
        ),
        model_router=router,
        tool_gateway=DenyAllToolGateway(),
        cancel_event=asyncio.Event(),
        session=db_session,
        model_call_ids=[],
    )
    state = await profile.graph_factory(deps).ainvoke({})
    plan = CharacterizationPlan.model_validate(
        (state.get("output") or {}).get("characterization_plan") or {"checks": [], "skipped": []}
    )
    assert plan.checks is not None or plan.skipped is not None
    assert len(deps.model_call_ids) >= 1
