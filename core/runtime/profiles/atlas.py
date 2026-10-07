from __future__ import annotations

import json
from typing import Any, TypedDict

from agents.atlas.schemas import ArchitectureDeltaProposal, ArchitectureProposal

from core.runtime.agent_profiles import AgentProfile, all_profiles, register_profile
from core.runtime.context import GraphDeps
from core.runtime.contracts import ModelRequest
from core.runtime.prompts.registry import load_prompt, render_prompt


class _AtlasState(TypedDict, total=False):
    output: dict[str, Any]
    model_call_ids: list[str]


def _build_atlas_graph(deps: GraphDeps) -> Any:
    from langgraph.graph import END, StateGraph

    async def propose_node(state: _AtlasState) -> _AtlasState:
        template = load_prompt("agents/atlas/prompts/propose_architecture.md")
        snap = deps.request.snapshot or {}
        system = render_prompt(
            template,
            {
                "project_name": str(snap.get("project_name", "project")),
                "approved_product_summary": str(snap.get("approved_product_summary", "")),
                "feature_specs_json": json.dumps(snap.get("feature_specs") or [], indent=2),
                "technology_constraints": str(snap.get("technology_constraints") or ""),
            },
        )
        result = await deps.model_router.invoke(
            ModelRequest(
                purpose="atlas.propose_architecture",
                alias=deps.profile.model_alias,
                system_instructions=system,
                context=list(deps.request.context),
                output_schema=ArchitectureProposal,
                tools=[],
                metadata={
                    "agent_profile": deps.profile.name,
                    "execution_id": str(deps.request.run_id),
                },
            )
        )
        deps.model_call_ids.append(result.model_call_id)
        if result.parsed_output is None:
            raise ValueError("Atlas did not return structured output")
        parsed = ArchitectureProposal.model_validate(result.parsed_output.model_dump())
        return {"output": parsed.model_dump(mode="json")}

    graph = StateGraph(_AtlasState)
    graph.add_node("propose", propose_node)
    graph.set_entry_point("propose")
    graph.add_edge("propose", END)
    return graph.compile()


def _build_atlas_delta_graph(deps: GraphDeps) -> Any:
    from langgraph.graph import END, StateGraph

    async def delta_node(state: _AtlasState) -> _AtlasState:
        template = load_prompt("agents/atlas/prompts/architecture_delta.md")
        snap = deps.request.snapshot or {}
        system = render_prompt(
            template,
            {
                "project_name": str(snap.get("project_name", "project")),
                "architecture_summary": str(snap.get("architecture_summary", "")),
                "impact_summary": str(snap.get("impact_summary", "")),
            },
        )
        result = await deps.model_router.invoke(
            ModelRequest(
                purpose="atlas.architecture_delta",
                alias=deps.profile.model_alias,
                system_instructions=system,
                context=list(deps.request.context),
                output_schema=ArchitectureDeltaProposal,
                tools=[],
                metadata={
                    "agent_profile": deps.profile.name,
                    "execution_id": str(deps.request.run_id),
                },
            )
        )
        deps.model_call_ids.append(result.model_call_id)
        if result.parsed_output is None:
            raise ValueError("Atlas architecture delta did not return structured output")
        parsed = ArchitectureDeltaProposal.model_validate(result.parsed_output.model_dump())
        return {"output": parsed.model_dump(mode="json")}

    graph = StateGraph(_AtlasState)
    graph.add_node("delta", delta_node)
    graph.set_entry_point("delta")
    graph.add_edge("delta", END)
    return graph.compile()


def register_atlas_profile() -> None:
    if "atlas.propose_architecture" not in all_profiles():
        register_profile(
            AgentProfile(
                name="atlas.propose_architecture",
                description="Propose project architecture from approved feature specs",
                model_alias="architecture",
                prompt_templates=("agents/atlas/prompts/propose_architecture.md",),
                output_schema=ArchitectureProposal,
                allowed_tools=(),
                graph_factory=_build_atlas_graph,
                max_steps=2,
            )
        )
    if "atlas.architecture_delta" not in all_profiles():
        register_profile(
            AgentProfile(
                name="atlas.architecture_delta",
                description="Propose architecture delta for feature changes",
                model_alias="architecture",
                prompt_templates=("agents/atlas/prompts/architecture_delta.md",),
                output_schema=ArchitectureDeltaProposal,
                allowed_tools=(),
                graph_factory=_build_atlas_delta_graph,
                max_steps=2,
            )
        )
