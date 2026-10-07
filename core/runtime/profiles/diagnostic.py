from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, Field, field_validator

from core.runtime.agent_profiles import AgentProfile, register_profile
from core.runtime.context import GraphDeps
from core.runtime.contracts import ContextItem, ModelRequest
from core.runtime.prompts.registry import load_prompt, render_prompt


class DiagnosticSummary(BaseModel):
    model_config = {"extra": "forbid"}

    title: str
    bullet_points: list[str] = Field(min_length=1, max_length=5)
    word_count_estimate: int

    @field_validator("bullet_points")
    @classmethod
    def bullet_count(cls, value: list[str]) -> list[str]:
        if not 1 <= len(value) <= 5:
            raise ValueError("bullet_points must contain 1 to 5 items")
        return value


class _EchoState(TypedDict, total=False):
    source_text: str
    output: dict[str, Any]
    model_call_ids: list[str]
    checkpoint_request: dict[str, Any]


def _build_graph(deps: GraphDeps) -> Any:
    from langgraph.graph import END, StateGraph

    async def summarize_node(state: _EchoState) -> _EchoState:
        if deps.cancel_event.is_set():
            from core.runtime.errors import RuntimeCancelled

            raise RuntimeCancelled()

        template = load_prompt("core/runtime/prompts/diagnostic_structured_echo.md")
        system = render_prompt(template, {"source_text": state.get("source_text", "")})
        meta: dict[str, str] = {
            "agent_profile": deps.profile.name,
            "prompt_template_id": template.template_id,
            "prompt_template_version": template.version,
            "prompt_hash": template.content_hash,
            "correlation_id": str(deps.request.run_id),
            "execution_id": str(deps.request.run_id),
        }
        if deps.request.contract and deps.request.contract.budgets.get("llm_usd") is not None:
            meta["budget_usd"] = str(deps.request.contract.budgets["llm_usd"])

        result = await deps.model_router.invoke(
            ModelRequest(
                purpose="diagnostic.structured_echo",
                alias=deps.profile.model_alias,
                system_instructions=system,
                context=[
                    ContextItem(
                        kind="TEXT",
                        content=state.get("source_text", ""),
                        provenance="DETERMINISTIC",
                    )
                ],
                output_schema=DiagnosticSummary,
                metadata=meta,
            )
        )
        deps.model_call_ids.append(result.model_call_id)
        assert result.parsed_output is not None
        return {
            "output": result.parsed_output.model_dump(),
            "model_call_ids": [str(mid) for mid in deps.model_call_ids],
        }

    graph = StateGraph(_EchoState)
    graph.add_node("summarize", summarize_node)
    graph.set_entry_point("summarize")
    graph.add_edge("summarize", END)
    return graph.compile()


def _build_ask_question_graph(deps: GraphDeps) -> Any:
    from langgraph.graph import END, StateGraph

    async def decide_node(state: _EchoState) -> _EchoState:
        source = state.get("source_text", "")
        if "[[AMBIGUOUS]]" in source:
            return {
                "checkpoint_request": {
                    "reason": "CLARIFICATION",
                    "questions": ["What should be clarified about the ambiguous input?"],
                }
            }
        template = load_prompt("core/runtime/prompts/diagnostic_structured_echo.md")
        system = render_prompt(template, {"source_text": source})
        meta: dict[str, str] = {
            "agent_profile": deps.profile.name,
            "correlation_id": str(deps.request.run_id),
            "execution_id": str(deps.request.run_id),
        }
        result = await deps.model_router.invoke(
            ModelRequest(
                purpose="diagnostic.ask_question",
                alias=deps.profile.model_alias,
                system_instructions=system,
                context=[
                    ContextItem(kind="TEXT", content=source, provenance="DETERMINISTIC"),
                ],
                output_schema=DiagnosticSummary,
                metadata=meta,
            )
        )
        deps.model_call_ids.append(result.model_call_id)
        assert result.parsed_output is not None
        return {
            "output": result.parsed_output.model_dump(),
            "model_call_ids": [str(mid) for mid in deps.model_call_ids],
        }

    graph = StateGraph(_EchoState)
    graph.add_node("decide", decide_node)
    graph.set_entry_point("decide")
    graph.add_edge("decide", END)
    return graph.compile()


def register_diagnostic_profile() -> None:
    from core.runtime.agent_profiles import all_profiles

    if "diagnostic.structured_echo" not in all_profiles():
        register_profile(
            AgentProfile(
                name="diagnostic.structured_echo",
                description="Minimal structured-output diagnostic agent",
                model_alias="verification_planning",
                prompt_templates=("core/runtime/prompts/diagnostic_structured_echo.md",),
                output_schema=DiagnosticSummary,
                allowed_tools=(),
                graph_factory=_build_graph,
                max_steps=5,
            )
        )
    if "diagnostic.ask_question" in all_profiles():
        return
    register_profile(
        AgentProfile(
            name="diagnostic.ask_question",
            description="Diagnostic agent that checkpoints on [[AMBIGUOUS]] input",
            model_alias="verification_planning",
            prompt_templates=(
                "core/runtime/prompts/diagnostic_ask_question.md",
                "core/runtime/prompts/diagnostic_structured_echo.md",
            ),
            output_schema=DiagnosticSummary,
            allowed_tools=(),
            graph_factory=_build_ask_question_graph,
            max_steps=5,
        )
    )
