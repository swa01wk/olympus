from __future__ import annotations

from core.commands.context import CommandContext
from core.domain.events.append import append_domain_event
from core.domain.projects.models import Project
from sqlalchemy.ext.asyncio import AsyncSession


class ProjectService:
    async def create(
        self,
        session: AsyncSession,
        key: str,
        name: str,
        description: str | None,
        ctx: CommandContext,
    ) -> Project:
        project = Project(key=key, name=name, description=description)
        session.add(project)
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="project",
            aggregate_id=project.id,
            event_type="project.created",
            payload={"key": key, "name": name},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=project.id,
        )
        return project
