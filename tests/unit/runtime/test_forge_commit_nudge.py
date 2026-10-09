"""Forge does not accept an ImplementationResult until the execution has a candidate commit."""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from agents.forge.schemas import ImplementationResult
from core.domain.enums import WorkType
from core.domain.task_contracts.schemas import TaskContractBody
from core.runtime.agent_profiles import clear_profiles, get_profile
from core.runtime.context import GraphDeps
from core.runtime.contracts import AgentRunRequest, ContextItem
from core.runtime.errors import SchemaValidationFailed
from core.runtime.model_router import ModelRouter
from core.runtime.profiles.forge import _MAX_COMMIT_NUDGES, register_forge_profile
from core.runtime.tool_client import DenyAllToolGateway

pytestmark = pytest.mark.unit

_RESULT = ImplementationResult(
    summary="done",
    changed_files=["app/api/tickets.py"],
    tests_added_or_changed=["tests/test_tickets.py"],
    test_commands_run=["pytest"],
    principal_symbols=["create_ticket"],
)


async def _run(commits: AsyncMock, invoke: AsyncMock | None = None) -> tuple[dict, AsyncMock]:
    clear_profiles()
    register_forge_profile()
    router = ModelRouter(MagicMock(), actor_id=uuid.uuid4(), providers={"fake": MagicMock()})
    profile = get_profile("forge.implementation")
    deps = GraphDeps(
        profile=profile,
        request=AgentRunRequest(
            run_id=uuid.uuid4(),
            agent_profile=profile.name,
            contract=TaskContractBody(
                objective="Add ticket priority",
                work_type=WorkType.CODE_CHANGE,
                inputs=[],
                executor_kind="AGENT_RUNTIME",
                allowed_scope=["app/api/**"],
            ),
            context=[ContextItem(kind="TEXT", content="implement", provenance="AGENT")],
            snapshot={},
        ),
        model_router=router,
        tool_gateway=DenyAllToolGateway(),
        cancel_event=asyncio.Event(),
        session=MagicMock(),
        model_call_ids=[],
    )
    invoke = invoke or AsyncMock(
        return_value=SimpleNamespace(
            tool_calls=[], parsed_output=_RESULT, model_call_id=uuid.uuid4()
        )
    )
    with (
        patch.object(router, "invoke", new=invoke),
        patch("core.runtime.profiles.forge._candidate_commit", new=commits),
    ):
        state = await profile.graph_factory(deps).ainvoke({})
    return state, invoke


@pytest.mark.asyncio
async def test_result_after_commit_is_accepted_immediately() -> None:
    state, invoke = await _run(AsyncMock(return_value=object()))
    assert invoke.await_count == 1
    assert state["output"] == _RESULT.model_dump()


@pytest.mark.asyncio
async def test_result_without_commit_is_sent_back_until_commit_exists() -> None:
    state, invoke = await _run(AsyncMock(side_effect=[None, object()]))
    assert invoke.await_count == 2
    retry_context = invoke.await_args_list[1].args[0].context[0].content
    assert "no candidate commit exists" in retry_context
    assert state["output"] == _RESULT.model_dump()


@pytest.mark.asyncio
async def test_nudges_are_bounded() -> None:
    state, invoke = await _run(AsyncMock(side_effect=[None] * _MAX_COMMIT_NUDGES))
    assert invoke.await_count == _MAX_COMMIT_NUDGES + 1
    assert state["output"] == _RESULT.model_dump()


@pytest.mark.asyncio
async def test_schema_failures_fall_back_to_the_committed_result() -> None:
    invalid = SchemaValidationFailed("bad", errors=[{"loc": ["summary"], "msg": "missing"}])
    commit = SimpleNamespace(changed_files=[{"path": "app/api/tickets.py"}])
    state, invoke = await _run(
        AsyncMock(return_value=commit), invoke=AsyncMock(side_effect=invalid)
    )
    # two failed implement calls, then the tool-less finalize call
    assert invoke.await_count == 3
    assert invoke.await_args_list[1].args[0].context[0].content.count("invalid schema") == 1
    assert invoke.await_args_list[2].args[0].purpose == "forge.implement.finalize"
    assert state["output"]["changed_files"] == ["app/api/tickets.py"]
