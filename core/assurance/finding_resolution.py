"""Resolve findings after remediation IC is READY."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.models import Finding
from core.commands.context import CommandContext
from core.domain.enums import TaskStatus
from core.domain.events.append import append_domain_event
from core.domain.tasks.models import Task
from core.integration.enums import FindingStatus
from core.integration.models import IntegrationCandidate


class FindingResolutionService:
    async def resolve_for_ic(
        self,
        session: AsyncSession,
        ic: IntegrationCandidate,
        ctx: CommandContext,
    ) -> list[uuid.UUID]:
        if ic.integrated_sha is None:
            return []
        findings = await session.execute(
            select(Finding).where(
                Finding.delivery_cycle_id == ic.delivery_cycle_id,
                Finding.status == FindingStatus.IN_REMEDIATION,
            )
        )
        resolved: list[uuid.UUID] = []
        for finding in findings.scalars():
            if finding.remediation_task_id is None:
                continue
            task = await session.get(Task, finding.remediation_task_id)
            if task is None or task.status != TaskStatus.COMPLETED:
                continue
            dup = await session.execute(
                select(Finding.id).where(
                    Finding.integration_candidate_id == ic.id,
                    Finding.fingerprint == finding.fingerprint,
                    Finding.status == FindingStatus.OPEN,
                )
            )
            if dup.scalar_one_or_none() is not None:
                continue
            finding.status = FindingStatus.RESOLVED
            finding.resolved_by_ic_id = ic.id
            finding.commit_sha = ic.integrated_sha
            await session.flush()
            resolved.append(finding.id)
            await append_domain_event(
                session,
                aggregate_type="finding",
                aggregate_id=finding.id,
                event_type="finding.resolved",
                payload={"ic_id": str(ic.id)},
                actor_id=ctx.actor.id,
                correlation_id=ctx.correlation_id,
                project_id=finding.project_id,
                delivery_cycle_id=finding.delivery_cycle_id,
            )
        return resolved
