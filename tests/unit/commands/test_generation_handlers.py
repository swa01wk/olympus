from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from core.commands.context import CommandContext
from core.commands.generation_handlers import (
    handle_architecture_delta_propose,
    handle_architecture_propose,
    handle_change_interpretation_rerun,
    handle_implementation_specs_generate,
    handle_release_create,
    handle_task_plan_generate,
)
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind, ActorRole

pytestmark = pytest.mark.unit

CYCLE = uuid.uuid4()


@pytest.fixture
def ctx() -> CommandContext:
    actor = Actor(kind=ActorKind.HUMAN, name="op", roles=[ActorRole.OPERATOR.value])
    return CommandContext(actor=actor, correlation_id="gen-test")


@pytest.mark.asyncio
async def test_architecture_propose_calls_orchestrator(ctx: CommandContext) -> None:
    with patch("core.commands.generation_handlers.PlanningOrchestrator") as mock_cls:
        inst = mock_cls.return_value
        inst.start_architecture_proposal = AsyncMock(return_value={"task_id": "t1"})
        out = await handle_architecture_propose(AsyncMock(), ctx, {"cycle_id": str(CYCLE)})
        inst.start_architecture_proposal.assert_awaited_once()
        assert out["task_id"] == "t1"


@pytest.mark.asyncio
async def test_implementation_specs_generate_calls_orchestrator(ctx: CommandContext) -> None:
    with patch("core.commands.generation_handlers.PlanningOrchestrator") as mock_cls:
        inst = mock_cls.return_value
        inst.start_implementation_spec_generation = AsyncMock(return_value=[{"task_id": "t2"}])
        out = await handle_implementation_specs_generate(AsyncMock(), ctx, {"cycle_id": str(CYCLE)})
        inst.start_implementation_spec_generation.assert_awaited_once()
        assert out["tasks"][0]["task_id"] == "t2"


@pytest.mark.asyncio
async def test_task_plan_generate_calls_orchestrator(ctx: CommandContext) -> None:
    with patch("core.commands.generation_handlers.PlanningOrchestrator") as mock_cls:
        inst = mock_cls.return_value
        inst.start_task_plan_generation = AsyncMock(return_value={"task_id": "t3"})
        out = await handle_task_plan_generate(AsyncMock(), ctx, {"cycle_id": str(CYCLE)})
        inst.start_task_plan_generation.assert_awaited_once()
        assert out["task_id"] == "t3"


@pytest.mark.asyncio
async def test_change_interpretation_rerun(ctx: CommandContext) -> None:
    with patch("core.commands.generation_handlers.FeatureChangeOrchestrator") as mock_cls:
        inst = mock_cls.return_value
        inst.schedule_change_interpret = AsyncMock(return_value={"interpret_task_id": "t4"})
        out = await handle_change_interpretation_rerun(AsyncMock(), ctx, {"cycle_id": str(CYCLE)})
        inst.schedule_change_interpret.assert_awaited_once()
        assert out["interpret_task_id"] == "t4"


@pytest.mark.asyncio
async def test_architecture_delta_propose(ctx: CommandContext) -> None:
    with patch("core.commands.generation_handlers.FeatureChangeOrchestrator") as mock_cls:
        inst = mock_cls.return_value
        inst.schedule_architecture_delta = AsyncMock(
            return_value={"architecture_delta_task_id": "t5"}
        )
        out = await handle_architecture_delta_propose(AsyncMock(), ctx, {"cycle_id": str(CYCLE)})
        inst.schedule_architecture_delta.assert_awaited_once()
        assert out["architecture_delta_task_id"] == "t5"


@pytest.mark.asyncio
async def test_release_create(ctx: CommandContext) -> None:
    release = type("R", (), {"id": uuid.uuid4(), "key": "REL-1"})()
    with patch("core.commands.generation_handlers.ReleaseService") as mock_cls:
        inst = mock_cls.return_value
        inst.create_release = AsyncMock(return_value=release)
        out = await handle_release_create(AsyncMock(), ctx, {"cycle_id": str(CYCLE)})
        inst.create_release.assert_awaited_once()
        assert out["key"] == "REL-1"
