"""Immutable evidence persistence."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.enums import EvidenceProducer, EvidenceResult, EvidenceType
from core.assurance.models import Evidence
from core.commands.context import CommandContext
from core.domain.events.append import append_domain_event
from core.domain.sequences import next_project_key


class EvidenceService:
    async def record(
        self,
        session: AsyncSession,
        *,
        project_id: uuid.UUID,
        delivery_cycle_id: uuid.UUID,
        integration_candidate_id: uuid.UUID | None,
        commit_sha: str,
        evidence_type: EvidenceType,
        result: EvidenceResult,
        subject_type: str,
        subject_id: uuid.UUID,
        check_ref: str,
        producer: EvidenceProducer,
        ctx: CommandContext,
        obligation_id: uuid.UUID | None = None,
        check_artifact_id: uuid.UUID | None = None,
        log_artifact_id: uuid.UUID | None = None,
        execution_id: uuid.UUID | None = None,
        carried_forward_from_id: uuid.UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> Evidence:
        key = await next_project_key(session, project_id, "evidence", prefix="EV")
        row = Evidence(
            key=key,
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
            integration_candidate_id=integration_candidate_id,
            commit_sha=commit_sha,
            evidence_type=evidence_type,
            result=result,
            subject_type=subject_type,
            subject_id=subject_id,
            obligation_id=obligation_id,
            check_ref=check_ref,
            check_artifact_id=check_artifact_id,
            log_artifact_id=log_artifact_id,
            producer=producer,
            execution_id=execution_id,
            carried_forward_from_id=carried_forward_from_id,
            details=details or {},
        )
        session.add(row)
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="evidence",
            aggregate_id=row.id,
            event_type="evidence.recorded",
            payload={
                "key": key,
                "evidence_type": evidence_type.value,
                "result": result.value,
                "commit_sha": commit_sha,
            },
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
        )
        return row
