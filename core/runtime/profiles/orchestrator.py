from __future__ import annotations

import json
from typing import Any, TypedDict

from agents.orchestrator.schemas import OrchestratorTurn

from core.commands.catalog import export_command_catalog
from core.orchestrator.service import fallback_turn
from core.runtime.agent_profiles import AgentProfile, all_profiles, register_profile
from core.runtime.context import GraphDeps
from core.runtime.contracts import ModelRequest
from core.runtime.prompts.registry import load_prompt, render_prompt


class _OrchState(TypedDict, total=False):
    output: dict[str, Any]
    model_call_ids: list[str]


def _build_graph(deps: GraphDeps) -> Any:
    from langgraph.graph import END, StateGraph

    async def converse_node(state: _OrchState) -> _OrchState:
        snap = deps.request.snapshot or {}
        template = load_prompt("agents/orchestrator/prompts/converse.md")
        system = render_prompt(
            template,
            {
                "user_message": str(snap.get("user_message") or ""),
                "snapshot_json": json.dumps(
                    {k: v for k, v in snap.items() if k != "user_message"},
                    indent=2,
                    default=str,
                ),
            },
        )
        result = await deps.model_router.invoke(
            ModelRequest(
                purpose="orchestration",
                alias=deps.profile.model_alias,
                system_instructions=system,
                context=[],
                output_schema=OrchestratorTurn,
                metadata={
                    "agent_profile": deps.profile.name,
                    "execution_id": str(deps.request.run_id),
                },
            )
        )
        deps.model_call_ids.append(result.model_call_id)
        catalog = export_command_catalog()
        if result.parsed_output is None:
            turn = fallback_turn(catalog)
        else:
            turn = OrchestratorTurn.model_validate(result.parsed_output.model_dump())
        return {"output": turn.model_dump(mode="json")}

    graph = StateGraph(_OrchState)
    graph.add_node("converse", converse_node)
    graph.set_entry_point("converse")
    graph.add_edge("converse", END)
    return graph.compile()


def register_orchestrator_profile() -> None:
    if "orchestrator.converse" in all_profiles():
        return
    register_profile(
        AgentProfile(
            name="orchestrator.converse",
            description="Operator orchestrator — explain state and propose typed commands",
            model_alias="orchestration",
            prompt_templates=("agents/orchestrator/prompts/converse.md",),
            output_schema=OrchestratorTurn,
            allowed_tools=(),
            graph_factory=_build_graph,
            max_steps=2,
        )
    )
