"""RL3.5 — approval notes become DECISION knowledge that reaches later agent prompts."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from core.commands.context import CommandContext
from core.commands.handlers import handle_approval_decide
from core.domain.approvals.models import Approval
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import (
    ApprovalStatus,
    DeliveryCycleType,
    ExecutionStatus,
    KnowledgeClass,
    TaskOrigin,
    WorkType,
)
from core.domain.executions.models import Execution
from core.domain.projects.models import Project
from core.domain.task_contracts.models import TaskContract
from core.domain.tasks.models import Task
from core.execution.snapshots.builder import SnapshotBuilder
from core.execution.snapshots.product_context import product_context_for_task
from core.planning.architecture.service import ArchitectureService
from core.product_model.models import KnowledgeItem
from core.review.service import RevisionService
from core.runtime.agent_profiles import get_profile
from core.runtime.context import GraphDeps
from core.runtime.contracts import AgentRunRequest, ModelRequest
from core.runtime.model_router import ModelRouter
from core.runtime.profiles.atlas import register_atlas_profile
from core.runtime.profiles.warden import register_warden_profile
from core.runtime.tool_client import DenyAllToolGateway
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.fixtures.brownfield_phase12_harness import ensure_human_approver
from tests.fixtures.planning_harness import supportdesk_architecture_proposal
from tests.fixtures.planning_workflow_harness import seed_supportdesk_product_and_approved_scope

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

NOTE = "Keep a single ProjectGuard for archive and close; no per-route checks."


async def _architecture_approval(
    session: AsyncSession, ctx: CommandContext, key: str
) -> tuple[DeliveryCycle, uuid.UUID]:
    project = Project(key=key, name=key)
    session.add(project)
    await session.flush()
    cycle = DeliveryCycle(
        project_id=project.id,
        key=f"C-{key}",
        type=DeliveryCycleType.GREENFIELD_BUILD,
        objective="decision notes",
        state="ARCHITECTURE",
        state_version=0,
        opened_by_actor_id=ctx.actor.id,
    )
    session.add(cycle)
    await session.flush()
    await seed_supportdesk_product_and_approved_scope(session, project.id, cycle.id, ctx)
    arch = await ArchitectureService().persist_proposal(
        session,
        project_id=project.id,
        proposal=supportdesk_architecture_proposal(),
        execution_id=None,
        ctx=ctx,
        delivery_cycle_id=cycle.id,
    )
    approval_id = await ArchitectureService().request_approval(session, arch.id, cycle.id, ctx)
    return cycle, approval_id


async def _decision_items(session: AsyncSession, cycle_id: uuid.UUID) -> list[KnowledgeItem]:
    return list(
        (
            await session.execute(
                select(KnowledgeItem).where(
                    KnowledgeItem.delivery_cycle_id == cycle_id,
                    KnowledgeItem.knowledge_class == KnowledgeClass.DECISION,
                )
            )
        ).scalars()
    )


async def _later_task(session: AsyncSession, cycle: DeliveryCycle) -> Task:
    task = Task(
        delivery_cycle_id=cycle.id,
        key=f"T-{uuid.uuid4().hex[:6]}",
        title="Later downstream work",
        work_type=WorkType.ANALYSIS,
        origin=TaskOrigin.CONTROL_PLANE,
    )
    session.add(task)
    await session.flush()
    return task


async def _rendered_system_prompt(profile_name: str, snapshot: dict[str, Any]) -> str:
    register_atlas_profile()
    register_warden_profile()
    profile = get_profile(profile_name)
    router = ModelRouter(MagicMock(), actor_id=uuid.uuid4(), providers={"fake": MagicMock()})
    captured: list[ModelRequest] = []

    async def _capture(request: ModelRequest) -> None:
        captured.append(request)
        raise RuntimeError("stop")

    deps = GraphDeps(
        profile=profile,
        request=AgentRunRequest(
            run_id=uuid.uuid4(),
            agent_profile=profile.name,
            contract=None,
            context=[],
            snapshot=snapshot,
        ),
        model_router=router,
        tool_gateway=DenyAllToolGateway(),
        cancel_event=asyncio.Event(),
        session=None,
        model_call_ids=[],
    )
    with (
        patch.object(router, "invoke", new=AsyncMock(side_effect=_capture)),
        pytest.raises(RuntimeError, match="stop"),
    ):
        await profile.graph_factory(deps).ainvoke({})
    assert len(captured) == 1
    return captured[0].system_instructions


async def test_approval_note_reaches_later_agent_prompts(db_session) -> None:
    _, human_ctx = await ensure_human_approver(db_session)
    cycle, approval_id = await _architecture_approval(db_session, human_ctx, "rl3-dec-note")

    await handle_approval_decide(
        db_session,
        human_ctx,
        {
            "approval_id": str(approval_id),
            "decision": ApprovalStatus.CHANGES_REQUESTED.value,
            "note": NOTE,
        },
    )

    approval = await db_session.get(Approval, approval_id)
    assert approval is not None
    statement = f"ARCHITECTURE {approval.key}: {NOTE}"
    decisions = await _decision_items(db_session, cycle.id)
    assert [d.statement for d in decisions] == [statement]
    assert decisions[0].subject_refs == [{"ref_type": "APPROVAL", "ref_id": str(approval_id)}]
    assert decisions[0].provenance["origin"] == "HUMAN"
    assert decisions[0].provenance["actor_id"] == str(human_ctx.actor.id)

    later = await _later_task(db_session, cycle)
    product_ctx = await product_context_for_task(db_session, later)
    assert product_ctx["decision_items"] == [statement]
    assert product_ctx["decision_context"] == f"Prior decisions:\n- {statement}"

    revision_task_id = await RevisionService().find_revision_task_id(
        db_session, approval_id, cycle.id
    )
    assert revision_task_id is not None
    contract = (
        await db_session.execute(
            select(TaskContract).where(TaskContract.task_id == revision_task_id)
        )
    ).scalar_one()
    execution = Execution(
        key=f"ex-{uuid.uuid4().hex[:6]}",
        task_id=revision_task_id,
        delivery_cycle_id=cycle.id,
        task_contract_id=contract.id,
        attempt_number=1,
        status=ExecutionStatus.QUEUED,
        executor_kind="AGENT_RUNTIME",
        agent_profile="atlas.propose_architecture",
    )
    db_session.add(execution)
    await db_session.flush()
    snapshot = await SnapshotBuilder().build(db_session, execution)
    assert snapshot.content["decision_items"] == [statement]

    for profile_name in ("atlas.propose_architecture", "warden.review"):
        system = await _rendered_system_prompt(profile_name, dict(snapshot.content))
        assert f"Prior decisions:\n- {statement}" in system, profile_name


async def test_approval_without_note_creates_no_decision(db_session) -> None:
    _, human_ctx = await ensure_human_approver(db_session)
    cycle, approval_id = await _architecture_approval(db_session, human_ctx, "rl3-dec-none")

    await handle_approval_decide(
        db_session,
        human_ctx,
        {"approval_id": str(approval_id), "decision": ApprovalStatus.APPROVED.value},
    )

    approval = await db_session.get(Approval, approval_id)
    assert approval is not None and approval.status == ApprovalStatus.APPROVED
    assert await _decision_items(db_session, cycle.id) == []
    product_ctx = await product_context_for_task(db_session, await _later_task(db_session, cycle))
    assert product_ctx["decision_items"] == []
    assert product_ctx["decision_context"] == ""


async def test_approval_with_blank_note_creates_no_decision(db_session) -> None:
    _, human_ctx = await ensure_human_approver(db_session)
    cycle, approval_id = await _architecture_approval(db_session, human_ctx, "rl3-dec-blank")

    await handle_approval_decide(
        db_session,
        human_ctx,
        {
            "approval_id": str(approval_id),
            "decision": ApprovalStatus.APPROVED.value,
            "note": "   ",
        },
    )

    assert await _decision_items(db_session, cycle.id) == []
