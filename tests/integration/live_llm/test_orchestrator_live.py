"""Phase 17 §11 — live Orchestrator converse over seeded control-plane state."""

from __future__ import annotations

import os
import uuid
from unittest.mock import patch

import pytest
from agents.orchestrator.schemas import OrchestratorTurn
from core.commands.context import CommandContext
from core.domain.enums import ActorKind, ApprovalStatus, ExecutionStatus
from core.domain.executions.models import Execution
from core.execution.worker import ExecutionWorker
from core.runtime.model_router import build_providers
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.fixtures.orchestrator_harness import (
    seed_blocking_finding_for_cycle,
    seed_open_clarification,
    seed_pending_scope_approval,
)
from tests.live_credentials import any_live_provider_configured

pytestmark = [pytest.mark.live_llm, pytest.mark.integration, pytest.mark.asyncio]


async def _run_orchestrator_turn(
    client: AsyncClient,
    factory: async_sessionmaker[AsyncSession],
    *,
    project_id: str,
    cycle_id: str,
    message: str,
) -> OrchestratorTurn:
    session_resp = await client.post(
        "/orchestrator/sessions",
        json={"project_id": project_id, "delivery_cycle_id": cycle_id},
    )
    assert session_resp.status_code == 201, session_resp.text
    session_id = session_resp.json()["id"]
    turn_resp = await client.post(
        f"/orchestrator/sessions/{session_id}/turns",
        json={"message": message},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert turn_resp.status_code == 200, turn_resp.text
    execution_id = uuid.UUID(turn_resp.json()["execution_id"])

    with patch("core.runtime.model_router.build_providers", side_effect=build_providers):
        async with factory() as session, session.begin():
            from core.domain.actors.models import Actor

            actor = (
                await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
            ).scalar_one_or_none()
            if actor is None:
                actor = Actor(kind=ActorKind.SYSTEM, name="orch-live-worker", roles=["SYSTEM"])
                session.add(actor)
                await session.flush()
            ctx = CommandContext(actor=actor, correlation_id="orch-live")
            worker = ExecutionWorker(worker_id=f"orch-{uuid.uuid4().hex[:6]}")
            for _ in range(25):
                await worker.run_once(session, ctx)
                ex = await session.get(Execution, execution_id)
                assert ex is not None
                if ex.status in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED}:
                    break

    async with factory() as session:
        ex = await session.get(Execution, execution_id)
        assert ex is not None
        assert ex.status == ExecutionStatus.COMPLETED, ex.failure_detail
        assert ex.output is not None
        return OrchestratorTurn.model_validate(ex.output)


@pytest.mark.skipif(os.getenv("LLM_LIVE_TESTS") != "1", reason="LLM_LIVE_TESTS not set")
async def test_orchestrator_answer_clarification(control_app, operator_token, async_engine) -> None:
    if not any_live_provider_configured():
        pytest.skip("No live provider API key configured")

    transport = ASGITransport(app=control_app)
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        project = await client.post(
            "/projects",
            json={"key": f"ORCH{uuid.uuid4().hex[:4].upper()}", "name": "Orch Clarify"},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        project_id = project.json()["id"]
        cycle = await client.post(
            f"/projects/{project_id}/delivery-cycles",
            json={"type": "GREENFIELD_BUILD", "objective": "orch"},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        cycle_id = cycle.json()["id"]

        async with factory() as session, session.begin():
            from core.domain.actors.models import Actor

            actor = (
                await session.execute(select(Actor).where(Actor.kind == ActorKind.HUMAN).limit(1))
            ).scalar_one()
            ctx = CommandContext(actor=actor, correlation_id="seed-cl")
            question = "How should closed tickets behave on update?"
            cl = await seed_open_clarification(
                session,
                project_id=uuid.UUID(project_id),
                delivery_cycle_id=uuid.UUID(cycle_id),
                question=question,
                ctx=ctx,
            )
            clarification_id = str(cl.id)

        turn = await _run_orchestrator_turn(
            client,
            factory,
            project_id=project_id,
            cycle_id=cycle_id,
            message="answer the open question: closed tickets return 409",
        )
        assert turn.intent in {"ANSWER_CLARIFICATION", "EXPLAIN"}
        if turn.intent == "ANSWER_CLARIFICATION":
            assert turn.clarification_answer_draft is not None
            assert turn.clarification_answer_draft.clarification_id == clarification_id
            assert "409" in turn.clarification_answer_draft.answer


@pytest.mark.skipif(os.getenv("LLM_LIVE_TESTS") != "1", reason="LLM_LIVE_TESTS not set")
async def test_orchestrator_propose_scope_command_draft_only(
    control_app, operator_token, async_engine
) -> None:
    if not any_live_provider_configured():
        pytest.skip("No live provider API key configured")

    transport = ASGITransport(app=control_app)
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        project = await client.post(
            "/projects",
            json={"key": f"ORP{uuid.uuid4().hex[:4].upper()}", "name": "Orch Proposal"},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        project_id = project.json()["id"]
        cycle = await client.post(
            f"/projects/{project_id}/delivery-cycles",
            json={"type": "GREENFIELD_BUILD", "objective": "orch proposal"},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        cycle_id = cycle.json()["id"]

        async with factory() as session, session.begin():
            from core.domain.actors.models import Actor

            actor = (
                await session.execute(select(Actor).where(Actor.kind == ActorKind.HUMAN).limit(1))
            ).scalar_one()
            ctx = CommandContext(actor=actor, correlation_id="seed-appr")
            await seed_pending_scope_approval(
                session,
                project_id=uuid.UUID(project_id),
                delivery_cycle_id=uuid.UUID(cycle_id),
                ctx=ctx,
            )

        turn = await _run_orchestrator_turn(
            client,
            factory,
            project_id=project_id,
            cycle_id=cycle_id,
            message="approve scope",
        )
        assert turn.intent in {"PROPOSE_COMMAND", "EXPLAIN", "OUT_OF_SCOPE"}
        if turn.intent == "PROPOSE_COMMAND":
            assert turn.proposed_command is not None
            assert turn.proposed_command.command != "approval.decide"

        async with factory() as session:
            from core.domain.approvals.models import Approval

            pending = (
                (
                    await session.execute(
                        select(Approval).where(
                            Approval.delivery_cycle_id == uuid.UUID(cycle_id),
                            Approval.status == ApprovalStatus.PENDING,
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert pending, "scope approval should remain pending (no auto-decide)"


@pytest.mark.skipif(os.getenv("LLM_LIVE_TESTS") != "1", reason="LLM_LIVE_TESTS not set")
async def test_orchestrator_explain_release_blockers(
    control_app, operator_token, async_engine
) -> None:
    if not any_live_provider_configured():
        pytest.skip("No live provider API key configured")

    transport = ASGITransport(app=control_app)
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {operator_token}"},
    ) as client:
        project = await client.post(
            "/projects",
            json={"key": f"ORB{uuid.uuid4().hex[:4].upper()}", "name": "Orch Blockers"},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        project_id = project.json()["id"]
        cycle = await client.post(
            f"/projects/{project_id}/delivery-cycles",
            json={"type": "GREENFIELD_BUILD", "objective": "orch blockers"},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        cycle_id = cycle.json()["id"]

        async with factory() as session, session.begin():
            from core.domain.actors.models import Actor

            actor = (
                await session.execute(select(Actor).where(Actor.kind == ActorKind.HUMAN).limit(1))
            ).scalar_one()
            ctx = CommandContext(actor=actor, correlation_id="seed-block")
            await seed_blocking_finding_for_cycle(
                session,
                project_id=uuid.UUID(project_id),
                delivery_cycle_id=uuid.UUID(cycle_id),
                ctx=ctx,
            )

        turn = await _run_orchestrator_turn(
            client,
            factory,
            project_id=project_id,
            cycle_id=cycle_id,
            message="what is blocking the release?",
        )
        assert turn.intent in {"EXPLAIN", "OUT_OF_SCOPE", "NAVIGATE"}
        if turn.intent == "EXPLAIN":
            assert turn.message
            assert turn.refs or "block" in turn.message.lower() or "release" in turn.message.lower()
