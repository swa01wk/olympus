from __future__ import annotations

import json
from typing import Any, TypedDict

from agents.warden.schemas import RootCauseHypothesis, WardenReview

from core.runtime.agent_profiles import AgentProfile, all_profiles, register_profile
from core.runtime.context import GraphDeps
from core.runtime.contracts import ModelRequest
from core.runtime.prompts.registry import load_prompt, render_prompt


class _WardenState(TypedDict, total=False):
    output: dict[str, Any]
    model_call_ids: list[str]


def _build_warden_graph(deps: GraphDeps) -> Any:
    from langgraph.graph import END, StateGraph

    async def review_node(state: _WardenState) -> _WardenState:
        template = load_prompt("agents/warden/prompts/review.md")
        snap = deps.request.snapshot or {}
        system = render_prompt(
            template,
            {
                "integrated_diff": str(snap.get("integrated_diff") or ""),
                "specs_json": json.dumps(snap.get("specs") or [], indent=2),
            },
        )
        result = await deps.model_router.invoke(
            ModelRequest(
                purpose="warden.review",
                alias=deps.profile.model_alias,
                system_instructions=system,
                context=list(deps.request.context),
                output_schema=WardenReview,
                tools=[],
                metadata={
                    "agent_profile": deps.profile.name,
                    "execution_id": str(deps.request.run_id),
                },
            )
        )
        deps.model_call_ids.append(result.model_call_id)
        if result.parsed_output is None:
            review = WardenReview(
                findings=[],
                recommendation="APPROVE",
                conformance=[],
                summary="No structured output",
            )
        else:
            review = WardenReview.model_validate(result.parsed_output.model_dump())
        return {"output": {"review": review.model_dump(mode="json")}}

    graph = StateGraph(_WardenState)
    graph.add_node("review", review_node)
    graph.set_entry_point("review")
    graph.add_edge("review", END)
    return graph.compile()


def _build_root_cause_graph(deps: GraphDeps) -> Any:
    from langgraph.graph import END, StateGraph

    async def rca_node(state: _WardenState) -> _WardenState:
        template = load_prompt("agents/warden/prompts/root_cause.md")
        snap = deps.request.snapshot or {}
        system = render_prompt(
            template, {"candidates_json": str(snap.get("candidates_json", "[]"))}
        )
        result = await deps.model_router.invoke(
            ModelRequest(
                purpose="warden.root_cause",
                alias=deps.profile.model_alias,
                system_instructions=system,
                context=list(deps.request.context),
                output_schema=RootCauseHypothesis,
                tools=[],
                metadata={
                    "agent_profile": deps.profile.name,
                    "execution_id": str(deps.request.run_id),
                },
            )
        )
        deps.model_call_ids.append(result.model_call_id)
        if result.parsed_output is None:
            raise ValueError("warden.root_cause missing output")
        hyp = RootCauseHypothesis.model_validate(result.parsed_output.model_dump())
        return {"output": {"hypothesis": hyp.model_dump(mode="json")}}

    graph = StateGraph(_WardenState)
    graph.add_node("root_cause", rca_node)
    graph.set_entry_point("root_cause")
    graph.add_edge("root_cause", END)
    return graph.compile()


def register_warden_profile() -> None:
    if "warden.review" not in all_profiles():
        register_profile(
            AgentProfile(
                name="warden.review",
                description="Independent engineering review for integration candidate",
                model_alias="review",
                prompt_templates=("agents/warden/prompts/review.md",),
                output_schema=WardenReview,
                allowed_tools=("repo.read", "git.diff"),
                graph_factory=_build_warden_graph,
                max_steps=2,
            )
        )
    if "warden.root_cause" not in all_profiles():
        register_profile(
            AgentProfile(
                name="warden.root_cause",
                description="Root-cause hypothesis for defect (INFERENCE)",
                model_alias="review",
                prompt_templates=("agents/warden/prompts/root_cause.md",),
                output_schema=RootCauseHypothesis,
                allowed_tools=("repo.read",),
                graph_factory=_build_root_cause_graph,
                max_steps=2,
            )
        )
