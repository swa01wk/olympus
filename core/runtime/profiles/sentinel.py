from __future__ import annotations

import json
from typing import Any, TypedDict

from agents.sentinel.schemas import (
    CharacterizationPlan,
    SentinelRecommendation,
    VerificationPlan,
)

from core.product_model.defects.schemas import ReproductionTestArtifact
from core.runtime.agent_profiles import AgentProfile, all_profiles, register_profile
from core.runtime.context import GraphDeps
from core.runtime.contracts import ModelRequest
from core.runtime.prompts.registry import load_prompt, render_prompt


class _SentinelState(TypedDict, total=False):
    output: dict[str, Any]
    model_call_ids: list[str]


def _json_text(value: object) -> str:
    """Snapshot lists arrive JSON-encoded from the contract ``_snapshot``."""
    if isinstance(value, str):
        return value
    return json.dumps(value or [], indent=2)


def _build_sentinel_plan_graph(deps: GraphDeps) -> Any:
    from langgraph.graph import END, StateGraph

    async def plan_node(state: _SentinelState) -> _SentinelState:
        template = load_prompt("agents/sentinel/prompts/plan.md")
        snap = deps.request.snapshot or {}
        decision_context = str(snap.get("decision_context") or "")
        if not decision_context:
            decisions = snap.get("decision_items") or []
            if decisions:
                decision_context = "Prior decisions:\n" + "\n".join(f"- {d}" for d in decisions)
        system = render_prompt(
            template,
            {
                "obligations_json": json.dumps(snap.get("obligations") or [], indent=2),
                "tests_json": json.dumps(snap.get("tests") or [], indent=2),
                "decision_context": decision_context,
            },
        )
        result = await deps.model_router.invoke(
            ModelRequest(
                purpose="sentinel.plan",
                alias=deps.profile.model_alias,
                system_instructions=system,
                context=list(deps.request.context),
                output_schema=VerificationPlan,
                tools=[],
                metadata={
                    "agent_profile": deps.profile.name,
                    "execution_id": str(deps.request.run_id),
                },
            )
        )
        deps.model_call_ids.append(result.model_call_id)
        if result.parsed_output is None:
            plan = VerificationPlan(checks=[], uncovered_obligations=[], notes=["empty"])
        else:
            plan = VerificationPlan.model_validate(result.parsed_output.model_dump())
        return {"output": {"verification_plan": plan.model_dump(mode="json")}}

    graph = StateGraph(_SentinelState)
    graph.add_node("plan", plan_node)
    graph.set_entry_point("plan")
    graph.add_edge("plan", END)
    return graph.compile()


def _build_sentinel_summarize_graph(deps: GraphDeps) -> Any:
    from langgraph.graph import END, StateGraph

    async def summarize_node(state: _SentinelState) -> _SentinelState:
        template = load_prompt("agents/sentinel/prompts/summarize.md")
        snap = deps.request.snapshot or {}
        system = render_prompt(
            template,
            {"evidence_summary": json.dumps(snap.get("evidence_summary") or {}, indent=2)},
        )
        result = await deps.model_router.invoke(
            ModelRequest(
                purpose="sentinel.summarize",
                alias=deps.profile.model_alias,
                system_instructions=system,
                context=list(deps.request.context),
                output_schema=SentinelRecommendation,
                tools=[],
                metadata={
                    "agent_profile": deps.profile.name,
                    "execution_id": str(deps.request.run_id),
                },
            )
        )
        deps.model_call_ids.append(result.model_call_id)
        if result.parsed_output is None:
            rec = SentinelRecommendation(
                recommended="PASS", uncovered_obligations=[], observations=[]
            )
        else:
            rec = SentinelRecommendation.model_validate(result.parsed_output.model_dump())
        return {"output": {"recommendation": rec.model_dump(mode="json")}}

    graph = StateGraph(_SentinelState)
    graph.add_node("summarize", summarize_node)
    graph.set_entry_point("summarize")
    graph.add_edge("summarize", END)
    return graph.compile()


def _build_sentinel_characterize_graph(deps: GraphDeps) -> Any:
    from langgraph.graph import END, StateGraph

    async def characterize_node(state: _SentinelState) -> _SentinelState:
        template = load_prompt("agents/sentinel/prompts/characterize.md")
        snap = deps.request.snapshot or {}
        system = render_prompt(
            template,
            {
                "acs_json": _json_text(snap.get("acs")),
                "behaviors_json": _json_text(snap.get("behaviors")),
                "index_summary": str(snap.get("index_summary", "[]")),
                "code_excerpt": str(snap.get("code_excerpt", "")),
            },
        )
        result = await deps.model_router.invoke(
            ModelRequest(
                purpose="sentinel.characterize",
                alias=deps.profile.model_alias,
                system_instructions=system,
                context=list(deps.request.context),
                output_schema=CharacterizationPlan,
                tools=[],
                metadata={
                    "agent_profile": deps.profile.name,
                    "execution_id": str(deps.request.run_id),
                },
            )
        )
        deps.model_call_ids.append(result.model_call_id)
        if result.parsed_output is None:
            plan = CharacterizationPlan(checks=[], skipped=[])
        else:
            plan = CharacterizationPlan.model_validate(result.parsed_output.model_dump())
        return {"output": plan.model_dump(mode="json")}

    graph = StateGraph(_SentinelState)
    graph.add_node("characterize", characterize_node)
    graph.set_entry_point("characterize")
    graph.add_edge("characterize", END)
    return graph.compile()


def register_sentinel_profiles() -> None:
    if "sentinel.plan" not in all_profiles():
        register_profile(
            AgentProfile(
                name="sentinel.plan",
                description="Plan verification checks for obligations",
                model_alias="verification_planning",
                prompt_templates=("agents/sentinel/prompts/plan.md",),
                output_schema=VerificationPlan,
                allowed_tools=("repo.read", "repo.list"),
                graph_factory=_build_sentinel_plan_graph,
                max_steps=2,
            )
        )
    if "sentinel.summarize" not in all_profiles():
        register_profile(
            AgentProfile(
                name="sentinel.summarize",
                description="Summarize verification evidence (recommendation only)",
                model_alias="verification_planning",
                prompt_templates=("agents/sentinel/prompts/summarize.md",),
                output_schema=SentinelRecommendation,
                allowed_tools=(),
                graph_factory=_build_sentinel_summarize_graph,
                max_steps=2,
            )
        )
    if "sentinel.reproduce" not in all_profiles():

        def _repro_factory(deps: GraphDeps) -> Any:
            from langgraph.graph import END, StateGraph

            async def repro_node(state: _SentinelState) -> _SentinelState:
                template = load_prompt("agents/sentinel/prompts/reproduce.md")
                snap = deps.request.snapshot or {}
                system = render_prompt(
                    template,
                    {
                        "triage_json": str(snap.get("triage_json", "")),
                        "defect_description": str(snap.get("defect_description", "")),
                        "index_summary": str(snap.get("index_summary", "")),
                        "code_excerpt": str(snap.get("code_excerpt", "")),
                    },
                )
                result = await deps.model_router.invoke(
                    ModelRequest(
                        purpose="sentinel.reproduce",
                        alias=deps.profile.model_alias,
                        system_instructions=system,
                        context=list(deps.request.context),
                        output_schema=ReproductionTestArtifact,
                        tools=[],
                        metadata={
                            "agent_profile": deps.profile.name,
                            "execution_id": str(deps.request.run_id),
                        },
                    )
                )
                deps.model_call_ids.append(result.model_call_id)
                if result.parsed_output is None:
                    raise ValueError("sentinel.reproduce missing output")
                parsed = ReproductionTestArtifact.model_validate(result.parsed_output.model_dump())
                return {"output": parsed.model_dump(mode="json")}

            graph = StateGraph(_SentinelState)
            graph.add_node("reproduce", repro_node)
            graph.set_entry_point("reproduce")
            graph.add_edge("reproduce", END)
            return graph.compile()

        register_profile(
            AgentProfile(
                name="sentinel.reproduce",
                description="Author defect reproduction pytest",
                model_alias="verification_planning",
                prompt_templates=("agents/sentinel/prompts/reproduce.md",),
                output_schema=ReproductionTestArtifact,
                allowed_tools=("fs.write",),
                graph_factory=_repro_factory,
                max_steps=2,
            )
        )
    if "sentinel.characterize" not in all_profiles():
        register_profile(
            AgentProfile(
                name="sentinel.characterize",
                description="Author characterization checks for recovered behavior",
                model_alias="verification_planning",
                prompt_templates=("agents/sentinel/prompts/characterize.md",),
                output_schema=CharacterizationPlan,
                allowed_tools=("repo.read", "repo.list"),
                graph_factory=_build_sentinel_characterize_graph,
                max_steps=2,
            )
        )
