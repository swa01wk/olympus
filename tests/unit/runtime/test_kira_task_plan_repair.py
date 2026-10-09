"""Kira task_plan makes one repair call when its plan fails the task-plan check."""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from core.planning.schemas import TaskPlan
from core.runtime.agent_profiles import clear_profiles, get_profile
from core.runtime.context import GraphDeps
from core.runtime.contracts import AgentRunRequest, ContextItem
from core.runtime.model_router import ModelRouter
from core.runtime.profiles.kira import register_kira_profile
from core.runtime.tool_client import DenyAllToolGateway
from tests.fixtures.planning_harness import minimal_task_plan

pytestmark = pytest.mark.unit


def _versioned_ref(plan: TaskPlan) -> TaskPlan:
    tasks = [
        t.model_copy(update={"implementation_spec_ref": f"{t.implementation_spec_ref}@v2"})
        for t in plan.tasks
    ]
    return plan.model_copy(update={"tasks": tasks})


async def _run(
    outputs: list[TaskPlan], errors: list[list[str]]
) -> tuple[dict, AsyncMock, AsyncMock]:
    clear_profiles()
    register_kira_profile()
    router = ModelRouter(MagicMock(), actor_id=uuid.uuid4(), providers={"fake": MagicMock()})
    profile = get_profile("kira.task_plan")
    deps = GraphDeps(
        profile=profile,
        request=AgentRunRequest(
            run_id=uuid.uuid4(),
            agent_profile=profile.name,
            contract=None,
            context=[ContextItem(kind="TEXT", content="plan", provenance="AGENT")],
            snapshot={"project_name": "demo", "implementation_specs_json": "[]"},
        ),
        model_router=router,
        tool_gateway=DenyAllToolGateway(),
        cancel_event=asyncio.Event(),
        session=MagicMock(),
        model_call_ids=[],
    )
    invoke = AsyncMock(
        side_effect=[SimpleNamespace(parsed_output=o, model_call_id=uuid.uuid4()) for o in outputs]
    )
    check = AsyncMock(side_effect=errors)
    with (
        patch.object(router, "invoke", new=invoke),
        patch("core.runtime.profiles.kira._task_plan_errors", new=check),
    ):
        state = await profile.graph_factory(deps).ainvoke({})
    return state, invoke, check


@pytest.mark.asyncio
async def test_valid_plan_makes_no_repair_call() -> None:
    plan = minimal_task_plan()
    state, invoke, check = await _run([plan], [[]])
    assert invoke.await_count == 1
    assert check.await_count == 1
    assert state["output"] == plan.model_dump(mode="json")


@pytest.mark.asyncio
async def test_invalid_plan_is_repaired_once_with_check_errors() -> None:
    plan = minimal_task_plan()
    error = f"unknown implementation_spec_ref: {plan.tasks[0].implementation_spec_ref}@v2"
    state, invoke, check = await _run([_versioned_ref(plan), plan], [[error]])

    assert invoke.await_count == 2
    assert check.await_count == 1
    repair_request = invoke.await_args_list[1].args[0]
    assert repair_request.purpose == "kira.task_plan.repair"
    assert error in repair_request.system_instructions
    assert "Revision request" in repair_request.system_instructions
    assert state["output"] == plan.model_dump(mode="json")
