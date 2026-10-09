"""RL2.1 — revision_feedback and previous_output_json in Kira/Atlas prompts."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from core.runtime.agent_profiles import clear_profiles, get_profile
from core.runtime.context import GraphDeps
from core.runtime.contracts import AgentRunRequest, ContextItem
from core.runtime.model_router import ModelRouter
from core.runtime.profiles.atlas import register_atlas_profile
from core.runtime.profiles.kira import register_kira_profile
from core.runtime.prompts.registry import load_prompt, render_prompt
from core.runtime.tool_client import DenyAllToolGateway

pytestmark = pytest.mark.unit

_REVISION_KEYS = {"revision_feedback": "", "previous_output_json": ""}
_REVISION_ACTIVE = {
    "revision_feedback": "Use one guard for archive.",
    "previous_output_json": '{"decisions": []}',
}

_KIRA_PROMPTS: list[tuple[str, dict[str, str]]] = [
    (
        "agents/kira/prompts/decompose.md",
        {
            "project_name": "p",
            "source_text": "doc",
            "decision_context": "",
            "approved_product_summary": "",
        },
    ),
    (
        "agents/kira/prompts/change_interpret.md",
        {
            "project_name": "p",
            "change_request_text": "change",
            "candidate_features_json": "[]",
            "architecture_summary": "{}",
        },
    ),
    (
        "agents/kira/prompts/implementation_spec.md",
        {
            "project_name": "p",
            "feature_spec_key": "FEAT-1",
            "architecture_summary": "{}",
            "feature_spec_body": "{}",
            "acceptance_criteria": "[]",
        },
    ),
    (
        "agents/kira/prompts/implementation_spec_delta.md",
        {
            "project_name": "p",
            "feature_spec_key": "FEAT-1",
            "feature_spec_body": "{}",
            "acceptance_criteria": "[]",
            "architecture_summary": "{}",
            "parent_implementation_spec_json": "{}",
            "impact_assessment_json": "[]",
        },
    ),
    (
        "agents/kira/prompts/implementation_spec_repair.md",
        {
            "project_name": "p",
            "architecture_summary": "{}",
            "root_cause_summary": "bug",
            "root_cause_json": "{}",
            "expected_behavior": "409",
            "impact_assessment_json": "[]",
            "expected_ac_keys": "AC-1",
            "reproduction_artifact_ref": "art",
            "max_repair_files": "3",
        },
    ),
    (
        "agents/kira/prompts/task_plan.md",
        {
            "project_name": "p",
            "implementation_specs_json": "[]",
            "mandatory_ac_keys": "AC-1",
            "repo_listing": "app/",
        },
    ),
]

_ATLAS_PROMPTS: list[tuple[str, dict[str, str]]] = [
    (
        "agents/atlas/prompts/propose_architecture.md",
        {
            "project_name": "p",
            "approved_product_summary": "summary",
            "feature_specs_json": "[]",
            "technology_constraints": "",
        },
    ),
    (
        "agents/atlas/prompts/architecture_delta.md",
        {
            "project_name": "p",
            "architecture_summary": "{}",
            "impact_summary": "impact",
        },
    ),
]


@pytest.mark.parametrize("path,base_vars", _KIRA_PROMPTS + _ATLAS_PROMPTS)
def test_revision_prompt_renders_without_revision_block(
    path: str, base_vars: dict[str, str]
) -> None:
    template = load_prompt(path)
    rendered = render_prompt(template, {**base_vars, **_REVISION_KEYS})
    assert "Revision request" not in rendered


@pytest.mark.parametrize("path,base_vars", _KIRA_PROMPTS + _ATLAS_PROMPTS)
def test_revision_prompt_renders_with_revision_block(path: str, base_vars: dict[str, str]) -> None:
    template = load_prompt(path)
    rendered = render_prompt(template, {**base_vars, **_REVISION_ACTIVE})
    assert "Revision request" in rendered
    assert _REVISION_ACTIVE["revision_feedback"] in rendered
    assert _REVISION_ACTIVE["previous_output_json"] in rendered


@pytest.mark.asyncio
async def test_kira_profiles_pass_revision_vars_to_render() -> None:
    clear_profiles()
    register_kira_profile()
    session = MagicMock()
    router = ModelRouter(session, actor_id=uuid.uuid4(), providers={"fake": MagicMock()})

    captured: list[dict[str, object]] = []

    def _capture_render(template: object, values: dict[str, object]) -> str:
        captured.append(dict(values))
        return "system"

    profile = get_profile("kira.decompose")
    snap = {
        "project_name": "demo",
        "revision_feedback": "note",
        "previous_output_json": '{"v":1}',
    }
    deps = GraphDeps(
        profile=profile,
        request=AgentRunRequest(
            run_id=uuid.uuid4(),
            agent_profile=profile.name,
            contract=None,
            context=[
                ContextItem(kind="TEXT", content="# Title\nbody", provenance="SOURCE_DOCUMENT")
            ],
            snapshot=snap,
        ),
        model_router=router,
        tool_gateway=DenyAllToolGateway(),
        cancel_event=asyncio.Event(),
        session=session,
        model_call_ids=[],
    )
    with (
        patch("core.runtime.profiles.kira.render_prompt", side_effect=_capture_render),
        patch.object(router, "invoke", new=AsyncMock(side_effect=RuntimeError("stop"))),
        pytest.raises(RuntimeError, match="stop"),
    ):
        await profile.graph_factory(deps).ainvoke({})
    assert captured
    assert captured[0]["revision_feedback"] == "note"
    assert captured[0]["previous_output_json"] == '{"v":1}'


@pytest.mark.asyncio
async def test_atlas_profiles_pass_revision_vars_to_render() -> None:
    clear_profiles()
    register_atlas_profile()
    session = MagicMock()
    router = ModelRouter(session, actor_id=uuid.uuid4(), providers={"fake": MagicMock()})

    captured: list[dict[str, object]] = []

    def _capture_render(template: object, values: dict[str, object]) -> str:
        captured.append(dict(values))
        return "system"

    profile = get_profile("atlas.propose_architecture")
    snap = {
        "project_name": "demo",
        "feature_specs": [],
        "revision_feedback": "consolidate guards",
        "previous_output_json": "{}",
    }
    deps = GraphDeps(
        profile=profile,
        request=AgentRunRequest(
            run_id=uuid.uuid4(),
            agent_profile=profile.name,
            contract=None,
            context=[],
            snapshot=snap,
        ),
        model_router=router,
        tool_gateway=DenyAllToolGateway(),
        cancel_event=asyncio.Event(),
        session=session,
        model_call_ids=[],
    )
    with (
        patch("core.runtime.profiles.atlas.render_prompt", side_effect=_capture_render),
        patch.object(router, "invoke", new=AsyncMock(side_effect=RuntimeError("stop"))),
        pytest.raises(RuntimeError, match="stop"),
    ):
        await profile.graph_factory(deps).ainvoke({})
    assert captured
    assert captured[0]["revision_feedback"] == "consolidate guards"
    assert captured[0]["previous_output_json"] == "{}"
