from __future__ import annotations

from typing import Any, TypedDict

from agents.kira.schemas import (
    ChangeInterpretation,
    ImplementationSpecDraft,
    ProductDecomposition,
    TaskPlan,
)

from core.config.settings import get_settings
from core.product_model.defects.schemas import DefectTriage, ExpectedBehaviorProposal
from core.product_model.source_chunking import (
    chunk_markdown_by_headings,
    merge_product_decompositions,
)
from core.runtime.agent_profiles import AgentProfile, all_profiles, register_profile
from core.runtime.context import GraphDeps
from core.runtime.contracts import ContextItem, ModelRequest
from core.runtime.prompts.registry import load_prompt, render_prompt


class _KiraState(TypedDict, total=False):
    source_text: str
    output: dict[str, Any]
    model_call_ids: list[str]


def _revision_vars(snap: dict[str, Any]) -> dict[str, str]:
    return {
        "revision_feedback": str(snap.get("revision_feedback", "")),
        "previous_output_json": str(snap.get("previous_output_json", "")),
    }


def _build_kira_graph(deps: GraphDeps) -> Any:
    from langgraph.graph import END, StateGraph

    async def decompose_node(state: _KiraState) -> _KiraState:
        template = load_prompt("agents/kira/prompts/decompose.md")
        source_text = state.get("source_text", "")
        for item in deps.request.context:
            if item.kind == "TEXT" and item.content:
                source_text = item.content
        project_name = "project"
        decision_context = ""
        approved_summary = ""
        if deps.request.snapshot:
            project_name = str(deps.request.snapshot.get("project_name", project_name))
            decisions = deps.request.snapshot.get("decision_items") or []
            if decisions:
                decision_context = "Prior decisions:\n" + "\n".join(f"- {d}" for d in decisions)
            approved_summary = str(deps.request.snapshot.get("approved_product_summary") or "")
        meta = {
            "agent_profile": deps.profile.name,
            "execution_id": str(deps.request.run_id),
        }
        max_chars = get_settings().product_source_decompose_max_chars
        chunks = chunk_markdown_by_headings(source_text, max_chars)
        merged: ProductDecomposition | None = None
        for chunk in chunks:
            chunk_system = render_prompt(
                template,
                {
                    "project_name": project_name,
                    "source_text": chunk,
                    "decision_context": decision_context,
                    "approved_product_summary": approved_summary,
                    **_revision_vars(deps.request.snapshot or {}),
                },
            )
            result = await deps.model_router.invoke(
                ModelRequest(
                    purpose="kira.decompose",
                    alias=deps.profile.model_alias,
                    system_instructions=chunk_system,
                    context=[
                        ContextItem(kind="TEXT", content=chunk, provenance="SOURCE_DOCUMENT"),
                    ],
                    output_schema=ProductDecomposition,
                    tools=[],
                    metadata={**meta, "source_chunk_count": str(len(chunks))},
                )
            )
            deps.model_call_ids.append(result.model_call_id)
            if result.parsed_output is None:
                raise ValueError("Kira decompose did not return structured output")
            parsed = ProductDecomposition.model_validate(result.parsed_output.model_dump())
            merged = parsed if merged is None else merge_product_decompositions(merged, parsed)
        assert merged is not None
        return {"output": merged.model_dump(mode="json"), "source_text": source_text}

    graph = StateGraph(_KiraState)
    graph.add_node("decompose", decompose_node)
    graph.set_entry_point("decompose")
    graph.add_edge("decompose", END)
    return graph.compile()


def _build_kira_planning_graph(
    deps: GraphDeps,
    *,
    purpose: str,
    prompt_path: str,
    output_schema: type[Any],
    template_keys: dict[str, str],
) -> Any:
    from langgraph.graph import END, StateGraph

    async def run_node(state: _KiraState) -> _KiraState:
        template = load_prompt(prompt_path)
        snap = deps.request.snapshot or {}
        values: dict[str, object] = {
            tpl: str(snap.get(snap_key, "")) for tpl, snap_key in template_keys.items()
        }
        values.update(_revision_vars(snap))
        system = render_prompt(template, values)
        result = await deps.model_router.invoke(
            ModelRequest(
                purpose=purpose,
                alias=deps.profile.model_alias,
                system_instructions=system,
                context=list(deps.request.context),
                output_schema=output_schema,
                tools=[],
                metadata={
                    "agent_profile": deps.profile.name,
                    "execution_id": str(deps.request.run_id),
                },
            )
        )
        deps.model_call_ids.append(result.model_call_id)
        if result.parsed_output is None:
            raise ValueError(f"{purpose} did not return structured output")
        parsed = output_schema.model_validate(result.parsed_output.model_dump())
        return {"output": parsed.model_dump(mode="json")}

    graph = StateGraph(_KiraState)
    graph.add_node("run", run_node)
    graph.set_entry_point("run")
    graph.add_edge("run", END)
    return graph.compile()


def register_kira_profile() -> None:
    if "kira.decompose" not in all_profiles():
        register_profile(
            AgentProfile(
                name="kira.decompose",
                description="Product source decomposition into capabilities, features, and specs",
                model_alias="product_decomposition",
                prompt_templates=("agents/kira/prompts/decompose.md",),
                output_schema=ProductDecomposition,
                allowed_tools=(),
                graph_factory=_build_kira_graph,
                max_steps=4,
            )
        )
    if "kira.implementation_spec" not in all_profiles():

        def _impl_factory(deps: GraphDeps) -> Any:
            snap = deps.request.snapshot or {}
            mode = str(snap.get("implementation_spec_mode"))
            if mode == "DELTA":
                prompt_path = "agents/kira/prompts/implementation_spec_delta.md"
            elif mode == "REPAIR":
                prompt_path = "agents/kira/prompts/implementation_spec_repair.md"
            else:
                prompt_path = "agents/kira/prompts/implementation_spec.md"
            keys = {
                "project_name": "project_name",
                "feature_spec_key": "feature_spec_key",
                "architecture_summary": "architecture_summary",
                "feature_spec_body": "feature_spec_body",
                "acceptance_criteria": "acceptance_criteria",
            }
            if mode == "DELTA":
                keys["parent_implementation_spec_json"] = "parent_implementation_spec_json"
                keys["impact_assessment_json"] = "impact_assessment_json"
            elif mode == "REPAIR":
                keys = {
                    "project_name": "project_name",
                    "root_cause_summary": "root_cause_summary",
                    "impact_assessment_json": "impact_assessment_json",
                    "expected_ac_keys": "expected_ac_keys",
                    "reproduction_artifact_ref": "reproduction_artifact_ref",
                    "max_repair_files": "max_repair_files",
                }
            return _build_kira_planning_graph(
                deps,
                purpose="kira.implementation_spec",
                prompt_path=prompt_path,
                output_schema=ImplementationSpecDraft,
                template_keys=keys,
            )

        register_profile(
            AgentProfile(
                name="kira.implementation_spec",
                description="Draft implementation specification for a feature",
                model_alias="planning",
                prompt_templates=("agents/kira/prompts/implementation_spec.md",),
                output_schema=ImplementationSpecDraft,
                allowed_tools=(),
                graph_factory=_impl_factory,
                max_steps=2,
            )
        )
    if "kira.change_interpret" not in all_profiles():

        def _interpret_factory(deps: GraphDeps) -> Any:
            return _build_kira_planning_graph(
                deps,
                purpose="kira.change_interpret",
                prompt_path="agents/kira/prompts/change_interpret.md",
                output_schema=ChangeInterpretation,
                template_keys={
                    "project_name": "project_name",
                    "change_request_text": "change_request_text",
                    "candidate_features_json": "candidate_features_json",
                    "architecture_summary": "architecture_summary",
                },
            )

        register_profile(
            AgentProfile(
                name="kira.change_interpret",
                description="Interpret change request against existing features",
                model_alias="product_decomposition",
                prompt_templates=("agents/kira/prompts/change_interpret.md",),
                output_schema=ChangeInterpretation,
                allowed_tools=(),
                graph_factory=_interpret_factory,
                max_steps=2,
            )
        )
    if "kira.task_plan" not in all_profiles():

        def _plan_factory(deps: GraphDeps) -> Any:
            return _build_kira_planning_graph(
                deps,
                purpose="kira.task_plan",
                prompt_path="agents/kira/prompts/task_plan.md",
                output_schema=TaskPlan,
                template_keys={
                    "project_name": "project_name",
                    "implementation_specs_json": "implementation_specs_json",
                    "mandatory_ac_keys": "mandatory_ac_keys",
                    "repo_listing": "repo_listing",
                },
            )

        register_profile(
            AgentProfile(
                name="kira.task_plan",
                description="Generate implementation task plan DAG",
                model_alias="planning",
                prompt_templates=("agents/kira/prompts/task_plan.md",),
                output_schema=TaskPlan,
                allowed_tools=(),
                graph_factory=_plan_factory,
                max_steps=2,
            )
        )
    if "kira.defect_triage" not in all_profiles():

        def _triage_factory(deps: GraphDeps) -> Any:
            return _build_kira_planning_graph(
                deps,
                purpose="kira.defect_triage",
                prompt_path="agents/kira/prompts/defect_triage.md",
                output_schema=DefectTriage,
                template_keys={
                    "defect_title": "defect_title",
                    "defect_description": "defect_description",
                    "candidate_features_json": "candidate_features_json",
                    "affected_sha": "affected_sha",
                },
            )

        register_profile(
            AgentProfile(
                name="kira.defect_triage",
                description="Triage defect against product model",
                model_alias="product_decomposition",
                prompt_templates=("agents/kira/prompts/defect_triage.md",),
                output_schema=DefectTriage,
                allowed_tools=(),
                graph_factory=_triage_factory,
                max_steps=2,
            )
        )
    if "kira.expected_behavior" not in all_profiles():

        def _eb_factory(deps: GraphDeps) -> Any:
            return _build_kira_planning_graph(
                deps,
                purpose="kira.expected_behavior",
                prompt_path="agents/kira/prompts/expected_behavior.md",
                output_schema=ExpectedBehaviorProposal,
                template_keys={
                    "defect_description": "defect_description",
                    "triage_json": "triage_json",
                },
            )

        register_profile(
            AgentProfile(
                name="kira.expected_behavior",
                description="Resolve expected behavior for defect",
                model_alias="product_decomposition",
                prompt_templates=("agents/kira/prompts/expected_behavior.md",),
                output_schema=ExpectedBehaviorProposal,
                allowed_tools=(),
                graph_factory=_eb_factory,
                max_steps=2,
            )
        )
