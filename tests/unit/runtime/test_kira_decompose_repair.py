"""Kira decompose makes one repair call when its output fails product model validation."""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from core.domain.enums import EvidenceRequirement
from core.product_model.schemas import ProductDecomposition
from core.product_model.validation import validate_proposal
from core.runtime.agent_profiles import clear_profiles, get_profile
from core.runtime.context import GraphDeps
from core.runtime.contracts import AgentRunRequest, ContextItem
from core.runtime.model_router import ModelRouter
from core.runtime.profiles.kira import register_kira_profile
from core.runtime.tool_client import DenyAllToolGateway
from tests.fixtures.product_model_harness import supportdesk_decomposition

pytestmark = pytest.mark.unit


def _review_allowed_on_functional_ac(valid: ProductDecomposition) -> ProductDecomposition:
    acs = list(valid.acceptance_criteria)
    acs[0] = acs[0].model_copy(
        update={"mandatory": True, "evidence_requirement": EvidenceRequirement.REVIEW_ALLOWED}
    )
    invalid = valid.model_copy(update={"acceptance_criteria": acs})
    assert any("REVIEW_ALLOWED" in e for e in validate_proposal(invalid))
    return invalid


def _result(proposal: ProductDecomposition) -> SimpleNamespace:
    return SimpleNamespace(parsed_output=proposal, model_call_id=uuid.uuid4())


async def _run(outputs: list[ProductDecomposition]) -> tuple[dict, AsyncMock]:
    clear_profiles()
    register_kira_profile()
    session = MagicMock()
    router = ModelRouter(session, actor_id=uuid.uuid4(), providers={"fake": MagicMock()})
    profile = get_profile("kira.decompose")
    deps = GraphDeps(
        profile=profile,
        request=AgentRunRequest(
            run_id=uuid.uuid4(),
            agent_profile=profile.name,
            contract=None,
            context=[ContextItem(kind="TEXT", content="# PRD\nbody", provenance="SOURCE_DOCUMENT")],
            snapshot={"project_name": "demo"},
        ),
        model_router=router,
        tool_gateway=DenyAllToolGateway(),
        cancel_event=asyncio.Event(),
        session=session,
        model_call_ids=[],
    )
    invoke = AsyncMock(side_effect=[_result(o) for o in outputs])
    with patch.object(router, "invoke", new=invoke):
        state = await profile.graph_factory(deps).ainvoke({})
    return state, invoke


@pytest.mark.asyncio
async def test_valid_output_makes_no_repair_call() -> None:
    valid = supportdesk_decomposition()
    state, invoke = await _run([valid])
    assert invoke.await_count == 1
    assert state["output"] == valid.model_dump(mode="json")


@pytest.mark.asyncio
async def test_invalid_output_is_repaired_once_with_validation_errors() -> None:
    valid = supportdesk_decomposition()
    invalid = _review_allowed_on_functional_ac(valid)
    state, invoke = await _run([invalid, valid])

    assert invoke.await_count == 2
    repair_request = invoke.await_args_list[1].args[0]
    assert repair_request.purpose == "kira.decompose.repair"
    assert (
        "REVIEW_ALLOWED mandatory AC must be non-functional" in repair_request.system_instructions
    )
    assert "Revision request" in repair_request.system_instructions
    assert state["output"] == valid.model_dump(mode="json")


@pytest.mark.asyncio
async def test_repair_that_stays_invalid_is_left_for_the_validator() -> None:
    invalid = _review_allowed_on_functional_ac(supportdesk_decomposition())
    state, invoke = await _run([invalid, invalid])
    assert invoke.await_count == 2
    assert validate_proposal(ProductDecomposition.model_validate(state["output"]))
