"""BaselineSet creation and declare_ready side effects."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.canonical_json import sha256_hex
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ProjectReadiness
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.domain.projects.models import Project
from core.domain.sequences import next_project_key
from core.intelligence.baselines.enums import BaselineStatus, ReadinessResult
from core.intelligence.baselines.models import (
    BaselineSet,
    BaselineSetItem,
    BehavioralBaseline,
    ReadinessAssessment,
)
from core.release.models import DeliveryOutcome


class BaselineSetService:
    async def create_from_active_baselines(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        delivery_cycle_id: uuid.UUID,
        commit_sha: str,
        ctx: CommandContext,
    ) -> BaselineSet:
        baselines = (
            (
                await session.execute(
                    select(BehavioralBaseline).where(
                        BehavioralBaseline.project_id == project_id,
                        BehavioralBaseline.status == BaselineStatus.ACTIVE,
                        BehavioralBaseline.established_sha == commit_sha,
                    )
                )
            )
            .scalars()
            .all()
        )
        key = await next_project_key(session, project_id, "baseline_set", prefix="B")
        content = {
            "baseline_ids": [str(b.id) for b in baselines],
            "commit_sha": commit_sha,
        }
        content_hash = sha256_hex(content)
        bset = BaselineSet(
            project_id=project_id,
            key=key,
            commit_sha=commit_sha,
            content_hash=content_hash,
            delivery_cycle_id=delivery_cycle_id,
        )
        session.add(bset)
        await session.flush()
        for bl in baselines:
            session.add(BaselineSetItem(baseline_set_id=bset.id, baseline_id=bl.id))
        project = await session.get(Project, project_id)
        if project is not None:
            project.active_baseline_set_id = bset.id
        await append_domain_event(
            session,
            aggregate_type="baseline_set",
            aggregate_id=bset.id,
            event_type="baseline_set.created",
            payload={"key": key, "count": len(baselines)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
        )
        return bset

    async def declare_ready(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> BaselineSet:
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None:
            raise ValueError("cycle missing")
        assessment = (
            await session.execute(
                select(ReadinessAssessment)
                .where(ReadinessAssessment.delivery_cycle_id == cycle_id)
                .order_by(ReadinessAssessment.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if assessment is None or assessment.result != ReadinessResult.READY:
            raise ValueError("readiness assessment not READY")
        baselines = (
            (
                await session.execute(
                    select(BehavioralBaseline).where(
                        BehavioralBaseline.project_id == cycle.project_id,
                        BehavioralBaseline.status == BaselineStatus.ACTIVE,
                        BehavioralBaseline.established_sha == assessment.commit_sha,
                    )
                )
            )
            .scalars()
            .all()
        )
        if not baselines:
            raise DomainError(
                code="NO_ACTIVE_BASELINES",
                message="No ACTIVE baselines at the readiness assessment SHA",
            )
        key = await next_project_key(session, cycle.project_id, "baseline_set", prefix="B")
        content = {
            "baseline_ids": [str(b.id) for b in baselines],
            "commit_sha": assessment.commit_sha,
        }
        content_hash = sha256_hex(content)
        bset = BaselineSet(
            project_id=cycle.project_id,
            key=key,
            commit_sha=assessment.commit_sha,
            content_hash=content_hash,
            delivery_cycle_id=cycle_id,
        )
        session.add(bset)
        await session.flush()
        for bl in baselines:
            session.add(BaselineSetItem(baseline_set_id=bset.id, baseline_id=bl.id))
        project = await session.get(Project, cycle.project_id)
        if project is not None:
            project.active_baseline_set_id = bset.id
            project.readiness_state = ProjectReadiness.READY_FOR_CHANGE
        existing_outcome = (
            await session.execute(
                select(DeliveryOutcome).where(DeliveryOutcome.delivery_cycle_id == cycle_id)
            )
        ).scalar_one_or_none()
        if existing_outcome is None:
            session.add(
                DeliveryOutcome(
                    delivery_cycle_id=cycle_id,
                    content={
                        "result": "READY_FOR_CHANGE",
                        "baseline_set_id": str(bset.id),
                        "commit_sha": assessment.commit_sha,
                    },
                    result="READY_FOR_CHANGE",
                )
            )
            await session.flush()
        await append_domain_event(
            session,
            aggregate_type="baseline_set",
            aggregate_id=bset.id,
            event_type="baseline_set.created",
            payload={"key": key, "count": len(baselines)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=cycle.project_id,
            delivery_cycle_id=cycle_id,
        )
        await append_domain_event(
            session,
            aggregate_type="project",
            aggregate_id=cycle.project_id,
            event_type="project.ready_for_change",
            payload={"baseline_set_key": key},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=cycle.project_id,
            delivery_cycle_id=cycle_id,
        )
        return bset
