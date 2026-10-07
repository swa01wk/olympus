from __future__ import annotations

from typing import Any, TypedDict

from agents.scout.schemas import RecoveredFeatureSpec, RepositorySurvey

from core.runtime.agent_profiles import AgentProfile, all_profiles, register_profile
from core.runtime.context import GraphDeps
from core.runtime.contracts import ModelRequest, ToolSpec
from core.runtime.prompts.registry import load_prompt, render_prompt
from core.tools.catalog import TOOL_CATALOG


class _ScoutState(TypedDict, total=False):
    output: dict[str, Any]
    model_call_ids: list[str]


def _tool_specs(profile: AgentProfile) -> list[ToolSpec]:
    specs: list[ToolSpec] = []
    for name in profile.allowed_tools:
        tool = TOOL_CATALOG[name]
        specs.append(
            ToolSpec(
                name=name,
                description=f"{tool.resource}.{tool.action}",
                parameters_schema=tool.params_schema,
            )
        )
    return specs


def _build_survey_graph(deps: GraphDeps) -> Any:
    from langgraph.graph import END, StateGraph

    async def survey_node(state: _ScoutState) -> _ScoutState:
        template = load_prompt("agents/scout/prompts/survey.md")
        snap = deps.request.snapshot or {}
        system = render_prompt(
            template,
            {
                "project_name": str(snap.get("project_name", "project")),
                "discovery_json": str(snap.get("scout_discovery_json", "{}")),
                "index_summary": str(snap.get("scout_index_summary", "[]")),
                "behaviors_json": str(snap.get("scout_behaviors_json", "[]")),
            },
        )
        result = await deps.model_router.invoke(
            ModelRequest(
                purpose="scout.survey",
                alias=deps.profile.model_alias,
                system_instructions=system,
                context=list(deps.request.context),
                output_schema=RepositorySurvey,
                tools=[],
                metadata={
                    "agent_profile": deps.profile.name,
                    "execution_id": str(deps.request.run_id),
                },
            )
        )
        deps.model_call_ids.append(result.model_call_id)
        if result.parsed_output is None:
            raise ValueError("Scout survey did not return structured output")
        parsed = RepositorySurvey.model_validate(result.parsed_output.model_dump())
        return {"output": parsed.model_dump(mode="json")}

    graph = StateGraph(_ScoutState)
    graph.add_node("survey", survey_node)
    graph.set_entry_point("survey")
    graph.add_edge("survey", END)
    return graph.compile()


def _build_recover_graph(deps: GraphDeps) -> Any:
    from langgraph.graph import END, StateGraph

    async def recover_node(state: _ScoutState) -> _ScoutState:
        template = load_prompt("agents/scout/prompts/recover_feature.md")
        snap = deps.request.snapshot or {}
        system = render_prompt(
            template,
            {
                "project_name": str(snap.get("project_name", "project")),
                "feature_ref": str(snap.get("scout_feature_ref", "feature")),
                "feature_draft_json": str(snap.get("scout_feature_draft_json", "{}")),
                "behaviors_json": str(snap.get("scout_behaviors_json", "[]")),
                "code_excerpt": str(snap.get("scout_code_excerpt", "")),
            },
        )
        result = await deps.model_router.invoke(
            ModelRequest(
                purpose="scout.recover_feature",
                alias=deps.profile.model_alias,
                system_instructions=system,
                context=list(deps.request.context),
                output_schema=RecoveredFeatureSpec,
                tools=[],
                metadata={
                    "agent_profile": deps.profile.name,
                    "execution_id": str(deps.request.run_id),
                },
            )
        )
        deps.model_call_ids.append(result.model_call_id)
        if result.parsed_output is None:
            raise ValueError("Scout recover did not return structured output")
        parsed = RecoveredFeatureSpec.model_validate(result.parsed_output.model_dump())
        return {"output": parsed.model_dump(mode="json")}

    graph = StateGraph(_ScoutState)
    graph.add_node("recover", recover_node)
    graph.set_entry_point("recover")
    graph.add_edge("recover", END)
    return graph.compile()


def register_scout_profile() -> None:
    if "scout.survey" not in all_profiles():
        register_profile(
            AgentProfile(
                name="scout.survey",
                description="Brownfield repository survey",
                model_alias="repository_reasoning",
                prompt_templates=("agents/scout/prompts/survey.md",),
                output_schema=RepositorySurvey,
                allowed_tools=("repo.read", "repo.search"),
                graph_factory=_build_survey_graph,
            )
        )
    if "scout.recover_feature" not in all_profiles():
        register_profile(
            AgentProfile(
                name="scout.recover_feature",
                description="Recover feature specification from code",
                model_alias="repository_reasoning",
                prompt_templates=("agents/scout/prompts/recover_feature.md",),
                output_schema=RecoveredFeatureSpec,
                allowed_tools=("repo.read", "repo.search"),
                graph_factory=_build_recover_graph,
            )
        )
