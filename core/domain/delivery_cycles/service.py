from __future__ import annotations

import uuid

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import DeliveryCycleType, ProjectReadiness, RepositorySourceType
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.domain.repositories.models import Repository
from core.domain.sequences import next_project_key
from core.repositories.service import RepositoryService
from core.state.guards import GuardRegistry, guard_registry
from core.state.machines import DELIVERY_CYCLE_MACHINES
from core.state.transition_service import TransitionResult, TransitionService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class DeliveryCycleService:
    def __init__(
        self,
        repo_service: RepositoryService | None = None,
        transitions: TransitionService | None = None,
        guards: GuardRegistry | None = None,
    ) -> None:
        self.repo_service = repo_service or RepositoryService()
        self.transitions = transitions or TransitionService()
        self.guards = guards or guard_registry

    async def create(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        cycle_type: DeliveryCycleType,
        objective: str,
        ctx: CommandContext,
        repository_id: uuid.UUID | None = None,
    ) -> DeliveryCycle:
        repo: Repository | None = None
        if cycle_type == DeliveryCycleType.GREENFIELD_BUILD:
            existing = await session.execute(
                select(Repository).where(Repository.project_id == project_id)
            )
            repo = existing.scalar_one_or_none()
            if repo is None:
                repo = await self.repo_service.declare_managed(session, project_id, ctx)
            elif (
                repo.source_type != RepositorySourceType.GREENFIELD_MANAGED
                or repo.released_commit is not None
            ):
                raise DomainError(
                    code="GREENFIELD_REQUIRES_UNRELEASED_MANAGED_REPOSITORY",
                    message="Greenfield build requires an unreleased managed repository",
                )
            repository_id = repo.id
        else:
            if repository_id is None:
                existing = await session.execute(
                    select(Repository).where(Repository.project_id == project_id)
                )
                repo = existing.scalar_one_or_none()
                repository_id = repo.id if repo else None
            if repository_id is None:
                raise DomainError(
                    code="REPOSITORY_REQUIRED", message="Delivery cycle requires a repository"
                )
        machine = DELIVERY_CYCLE_MACHINES[cycle_type]
        key = await next_project_key(session, project_id, "delivery_cycle", prefix="DC")
        cycle = DeliveryCycle(
            project_id=project_id,
            key=key,
            type=cycle_type,
            objective=objective,
            state=machine.initial,
            repository_id=repository_id,
            opened_by_actor_id=ctx.actor.id,
        )
        session.add(cycle)
        await session.flush()
        if cycle_type == DeliveryCycleType.BROWNFIELD_ONBOARDING:
            from core.domain.projects.models import Project

            project = await session.get(Project, project_id)
            if project is not None:
                project.readiness_state = ProjectReadiness.ONBOARDING
        await append_domain_event(
            session,
            aggregate_type="delivery_cycle",
            aggregate_id=cycle.id,
            event_type="delivery_cycle.created",
            payload={"type": cycle_type.value, "key": key},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=project_id,
            delivery_cycle_id=cycle.id,
        )
        return cycle

    async def allowed_commands(
        self,
        session: AsyncSession,
        cycle: DeliveryCycle,
        ctx: CommandContext,
    ) -> list[dict[str, object]]:
        machine = DELIVERY_CYCLE_MACHINES[cycle.type]
        commands: list[dict[str, object]] = []
        for (state, command), edge in machine.edges.items():
            if state != cycle.state:
                continue
            preview: list[str] = []
            for guard_id in edge.guards:
                result = await self.guards.evaluate(guard_id, session, cycle, ctx)
                if not result.ok:
                    preview.extend(result.reasons)
            commands.append(
                {
                    "command": command,
                    "to_state": edge.to,
                    "guard_preview": preview,
                    "allowed": len(preview) == 0,
                }
            )
        return commands

    async def run_command(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        command: str,
        expected_state: str,
        ctx: CommandContext,
        payload: dict[str, object] | None = None,
    ) -> TransitionResult:
        return await self.transitions.transition(
            session,
            "delivery_cycle",
            cycle_id,
            expected_state,
            command,
            ctx,
            payload=payload,
        )
