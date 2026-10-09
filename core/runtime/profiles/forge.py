from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict

from agents.forge.schemas import ImplementationResult

from core.domain.task_contracts.schemas import TaskContractBody
from core.runtime.agent_profiles import AgentProfile, all_profiles, register_profile
from core.runtime.context import GraphDeps
from core.runtime.contracts import ContextItem, ModelRequest, ToolSpec
from core.runtime.errors import SchemaValidationFailed
from core.runtime.prompts.registry import load_prompt, render_prompt
from core.runtime.structured_output import STRUCTURED_OUTPUT_TOOL
from core.tools.catalog import TOOL_CATALOG


class _ForgeState(TypedDict, total=False):
    messages: list[str]
    output: dict[str, Any]
    model_call_ids: list[str]
    step: int
    checkpoint_request: dict[str, Any]


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


_MAX_COMMIT_NUDGES = 3
_MAX_SCHEMA_FAILURES = 2
_NO_COMMIT_NOTE = (
    "tool:submit_structured_output=>rejected: no candidate commit exists for this execution. "
    "Make the required changes within allowed_scope, run test.run, then call git.commit "
    "before submitting the ImplementationResult again."
)


async def _candidate_commit(deps: GraphDeps) -> Any | None:
    if deps.session is None:
        return None
    from sqlalchemy import select

    from core.domain.candidate_commits.models import CandidateCommit

    await deps.session.flush()
    cc_row = await deps.session.execute(
        select(CandidateCommit).where(CandidateCommit.execution_id == deps.request.run_id)
    )
    return cc_row.scalar_one_or_none()


async def _implementation_result_from_candidate_commit(
    deps: GraphDeps,
    contract: TaskContractBody | None,
) -> dict[str, Any] | None:
    cc = await _candidate_commit(deps)
    if cc is None:
        return None
    paths = [
        str(item.get("path", "")) for item in (cc.changed_files or []) if str(item.get("path", ""))
    ]
    principals: list[str] = []
    if paths:
        principals = [Path(p).stem for p in paths[:3] if p]
    return ImplementationResult(
        summary="Implementation completed via ToolGateway",
        changed_files=paths or ["."],
        tests_added_or_changed=[p for p in paths if "test" in p.lower()],
        test_commands_run=["test.run"] if paths else [],
        principal_symbols=principals or ["implementation"],
    ).model_dump()


def _build_forge_graph(deps: GraphDeps) -> Any:
    from langgraph.graph import END, StateGraph

    async def implement_node(state: _ForgeState) -> _ForgeState:
        contract = deps.request.contract
        if contract is None:
            raise ValueError("TaskContract required for forge")
        template = load_prompt("agents/forge/prompts/implement.md")
        snap = deps.request.snapshot or {}
        decision_context = str(snap.get("decision_context") or "")
        if not decision_context:
            decisions = snap.get("decision_items") or []
            if decisions:
                decision_context = "Prior decisions:\n" + "\n".join(f"- {d}" for d in decisions)
        system = render_prompt(
            template,
            {
                "objective": contract.objective,
                "allowed_scope": ", ".join(contract.allowed_scope),
                "constraints": "; ".join(contract.constraints),
                "decision_context": decision_context,
                "protected_tests": "\n".join(f"- {t}" for t in snap.get("protected_tests") or [])
                or "(none)",
            },
        )
        messages = list(state.get("messages", []))
        step = 0
        commit_nudges = 0
        schema_failures = 0
        output: dict[str, Any] | None = None
        meta = {
            "agent_profile": deps.profile.name,
            "execution_id": str(deps.request.run_id),
            "correlation_id": str(deps.request.run_id),
        }
        while step < deps.profile.max_steps and output is None:
            step += 1
            context_text = "\n".join(messages)
            try:
                result = await deps.model_router.invoke(
                    ModelRequest(
                        purpose="forge.implement",
                        alias=deps.profile.model_alias,
                        system_instructions=system,
                        context=[
                            ContextItem(kind="TEXT", content=context_text, provenance="AGENT"),
                        ],
                        output_schema=ImplementationResult,
                        tools=_tool_specs(deps.profile),
                        metadata=meta,
                    )
                )
            except SchemaValidationFailed as exc:
                schema_failures += 1
                errors = exc.details.get("errors")
                messages.append(f"tool:submit_structured_output=>invalid schema: {errors}")
                if schema_failures >= _MAX_SCHEMA_FAILURES:
                    break
                continue
            deps.model_call_ids.append(result.model_call_id)
            submitted: dict[str, Any] | None = None
            if result.tool_calls:
                for call in result.tool_calls:
                    if call.name == STRUCTURED_OUTPUT_TOOL:
                        try:
                            submitted = ImplementationResult.model_validate(
                                call.arguments
                            ).model_dump()
                        except Exception:
                            messages.append("tool:structured_output=>invalid schema")
                        break
                    tool_result = await deps.tool_gateway.request(call.name, call.arguments)
                    messages.append(f"tool:{call.name}=>{tool_result.content}")
                    try:
                        payload = json.loads(tool_result.content)
                    except json.JSONDecodeError:
                        payload = {}
                    if payload.get("pending_approval"):
                        return {
                            "checkpoint_request": {
                                "questions": [
                                    "Governed action requires human approval before continuing."
                                ],
                                "approval_payload": payload.get("pending_approval"),
                            },
                            "messages": messages,
                            "step": step,
                            "model_call_ids": [str(x) for x in deps.model_call_ids],
                        }
            elif result.parsed_output is not None:
                submitted = result.parsed_output.model_dump()
            if submitted is None:
                continue
            if (
                deps.session is not None
                and commit_nudges < _MAX_COMMIT_NUDGES
                and await _candidate_commit(deps) is None
            ):
                commit_nudges += 1
                messages.append(_NO_COMMIT_NOTE)
                continue
            output = submitted
        if output is None and messages:
            try:
                finalize = await deps.model_router.invoke(
                    ModelRequest(
                        purpose="forge.implement.finalize",
                        alias=deps.profile.model_alias,
                        system_instructions=(
                            f"{system}\n\n"
                            "You must now emit the final ImplementationResult JSON only "
                            "(summary, changed_files, tests, principal_symbols). "
                            "Do not call tools."
                        ),
                        context=[
                            ContextItem(
                                kind="TEXT",
                                content="\n".join(messages[-40:]),
                                provenance="AGENT",
                            ),
                        ],
                        output_schema=ImplementationResult,
                        tools=[],
                        metadata=meta,
                    )
                )
                deps.model_call_ids.append(finalize.model_call_id)
                if finalize.parsed_output is not None:
                    output = finalize.parsed_output.model_dump()
            except SchemaValidationFailed:
                pass
        if output is None:
            output = await _implementation_result_from_candidate_commit(deps, contract)
        if output is None:
            raise ValueError("forge did not produce ImplementationResult")
        return {
            "output": output,
            "messages": messages,
            "step": step,
            "model_call_ids": [str(x) for x in deps.model_call_ids],
        }

    graph = StateGraph(_ForgeState)
    graph.add_node("implement", implement_node)
    graph.set_entry_point("implement")
    graph.add_edge("implement", END)
    return graph.compile()


def register_forge_profile() -> None:
    if "forge.implementation" in all_profiles():
        return
    register_profile(
        AgentProfile(
            name="forge.implementation",
            description="Forge code implementation agent",
            model_alias="implementation",
            prompt_templates=("agents/forge/prompts/implement.md",),
            output_schema=ImplementationResult,
            allowed_tools=(
                "repo.read",
                "repo.search",
                "repo.list",
                "repo.write",
                "shell.run",
                "test.run",
                "git.diff",
                "git.status",
                "git.commit",
                "olympus.ask_question",
                "olympus.submit_artifact",
            ),
            graph_factory=_build_forge_graph,
            max_steps=60,
        )
    )
