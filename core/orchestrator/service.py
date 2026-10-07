from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from agents.orchestrator.schemas import OrchestratorTurn
from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind, ActorRole, TaskContractStatus, TaskOrigin, WorkType
from core.domain.events.append import append_domain_event
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody, VersionedRef
from core.domain.tasks.service import TaskService
from core.orchestrator.models import OrchestratorSession
from core.orchestrator.validator import OrchestratorValidationError, validate_turn
from core.scheduler.admission import AdmissionService
from core.views.read_models import build_cycle_overview, build_inbox_view, build_project_overview
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _as_utc(dt: datetime) -> datetime:
    """TIMESTAMP WITHOUT TIME ZONE round-trips as naive UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


async def _system_command_context(session: AsyncSession, correlation_id: str) -> CommandContext:
    actor = (
        await session.execute(select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1))
    ).scalar_one_or_none()
    if actor is None:
        actor = Actor(
            kind=ActorKind.SYSTEM,
            name="orchestrator-system",
            roles=[ActorRole.SYSTEM.value],
        )
        session.add(actor)
        await session.flush()
    return CommandContext(actor=actor, correlation_id=correlation_id)


class OrchestratorService:
    SESSION_TTL = timedelta(hours=8)

    async def create_session(
        self,
        session: AsyncSession,
        *,
        actor_id: uuid.UUID,
        project_id: uuid.UUID | None,
        delivery_cycle_id: uuid.UUID | None,
    ) -> OrchestratorSession:
        row = OrchestratorSession(
            actor_id=actor_id,
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
            turns=[],
            expires_at=(datetime.now(UTC) + self.SESSION_TTL).replace(tzinfo=None),
        )
        session.add(row)
        await session.flush()
        return row

    async def get_session(
        self, session: AsyncSession, session_id: uuid.UUID, actor_id: uuid.UUID
    ) -> OrchestratorSession:
        row = await session.get(OrchestratorSession, session_id)
        if row is None or row.actor_id != actor_id:
            raise ValueError("session not found")
        if _as_utc(row.expires_at) < datetime.now(UTC):
            raise ValueError("session expired")
        return row

    async def append_user_turn(
        self,
        session: AsyncSession,
        orch_session: OrchestratorSession,
        message: str,
        ctx: CommandContext,
    ) -> dict[str, str]:
        turns = list(orch_session.turns or [])
        turns.append({"role": "user", "text": message})
        orch_session.turns = turns
        await session.flush()
        if orch_session.delivery_cycle_id is None:
            raise ValueError("delivery_cycle_id required for orchestrator execution")
        execution_id = await self._schedule_converse(session, orch_session, message, ctx)
        turns.append({"role": "system", "text": "scheduled", "execution_id": execution_id})
        orch_session.turns = turns
        await session.flush()
        return {"execution_id": execution_id}

    async def complete_turn(
        self,
        session: AsyncSession,
        orch_session: OrchestratorSession,
        *,
        execution_id: uuid.UUID,
        turn: OrchestratorTurn,
        ctx: CommandContext,
    ) -> None:
        try:
            validated = validate_turn(turn, actor=ctx.actor)
        except OrchestratorValidationError:
            from core.commands.catalog import export_command_catalog

            validated = fallback_turn(export_command_catalog())
        turns = list(orch_session.turns or [])
        turns.append(
            {
                "role": "assistant",
                "text": validated.message,
                "execution_id": str(execution_id),
                "intent": validated.intent,
                "proposal": validated.proposed_command.model_dump(mode="json")
                if validated.proposed_command
                else None,
                "clarification_answer_draft": validated.clarification_answer_draft.model_dump(
                    mode="json"
                )
                if validated.clarification_answer_draft
                else None,
            }
        )
        orch_session.turns = turns
        await append_domain_event(
            session,
            aggregate_type="orchestrator_session",
            aggregate_id=orch_session.id,
            event_type="orchestrator.turn_completed",
            payload={
                "session_id": str(orch_session.id),
                "execution_id": str(execution_id),
                "intent": validated.intent,
            },
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=orch_session.project_id,
            delivery_cycle_id=orch_session.delivery_cycle_id,
        )

    async def build_snapshot(
        self,
        session: AsyncSession,
        orch_session: OrchestratorSession,
        ctx: CommandContext,
    ) -> dict[str, Any]:
        overview: dict[str, Any] = {}
        if orch_session.project_id:
            overview = await build_project_overview(session, orch_session.project_id, ctx)
        elif orch_session.delivery_cycle_id:
            overview = await build_cycle_overview(session, orch_session.delivery_cycle_id, ctx)
        inbox = await build_inbox_view(
            session,
            ctx,
            project_id=orch_session.project_id,
            delivery_cycle_id=orch_session.delivery_cycle_id,
        )
        from core.commands.catalog import export_command_catalog

        return {
            "overview": overview,
            "inbox": inbox,
            "command_catalog": export_command_catalog(),
            "session_turns": orch_session.turns,
        }

    async def _schedule_converse(
        self,
        session: AsyncSession,
        orch_session: OrchestratorSession,
        message: str,
        ctx: CommandContext,
    ) -> str:
        cycle_id = orch_session.delivery_cycle_id
        assert cycle_id is not None
        task = await TaskService().create_task(
            session,
            cycle_id,
            "Orchestrator converse",
            WorkType.ANALYSIS,
            TaskOrigin.CONTROL_PLANE,
            ctx,
            priority=10,
        )
        snapshot = await self.build_snapshot(session, orch_session, ctx)
        body = TaskContractBody(
            objective="Explain delivery state and propose typed operator commands",
            work_type=WorkType.ANALYSIS,
            inputs=[VersionedRef(ref_type="DELIVERY_CYCLE", ref_id=cycle_id)],
            executor_kind="AGENT_RUNTIME",
            agent_profile="orchestrator.converse",
            model_alias="orchestration",
            required_outputs=["artifact:ORCHESTRATOR_TURN"],
            budgets={"llm_usd": 0.25},
        )
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body={
                **body.model_dump(mode="json"),
                "_snapshot": {**snapshot, "user_message": message},
                "orchestrator_session_id": str(orch_session.id),
                "actor_kind": ctx.actor.kind.value,
                "actor_roles": list(ctx.actor.roles or []),
            },
            content_hash=f"orch-{orch_session.id}-{len(orch_session.turns)}",
            compiled_by="orchestrator",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        execution = await AdmissionService().admit_task(
            session, task.id, await _system_command_context(session, ctx.correlation_id)
        )
        return str(execution.id)


def fallback_turn(catalog: dict[str, Any]) -> OrchestratorTurn:
    names = [c["command"] for c in catalog.get("commands", [])][:12]
    return OrchestratorTurn(
        intent="EXPLAIN",
        message=("I could not interpret that; here are the available actions: " + ", ".join(names)),
        refs=[],
    )
