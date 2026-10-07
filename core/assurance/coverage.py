"""Acceptance coverage computation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.enums import EvidenceResult, ObligationStatus
from core.assurance.evidence_rules import evidence_satisfies_mandatory
from core.assurance.models import AcceptanceCoverage, Evidence, VerificationObligation
from core.commands.context import CommandContext
from core.domain.events.append import append_domain_event


class CoverageService:
    async def recompute_for_ic(
        self,
        session: AsyncSession,
        integration_candidate_id: uuid.UUID,
        ctx: CommandContext,
    ) -> list[AcceptanceCoverage]:
        obligations = await session.execute(
            select(VerificationObligation).where(
                VerificationObligation.integration_candidate_id == integration_candidate_id,
            )
        )
        evidence = await session.execute(
            select(Evidence).where(
                Evidence.integration_candidate_id == integration_candidate_id,
            )
        )
        ev_list = list(evidence.scalars())
        rows: list[AcceptanceCoverage] = []
        now = datetime.now(UTC)
        for obl in obligations.scalars():
            best: Evidence | None = None
            for ev in ev_list:
                if ev.obligation_id != obl.id:
                    continue
                if ev.result != EvidenceResult.PASS:
                    continue
                if not evidence_satisfies_mandatory(
                    ev.evidence_type.value,
                    list(obl.allowed_evidence_types or []),
                    required=obl.required,
                ):
                    continue
                best = ev
                break
            if best is not None:
                row = AcceptanceCoverage(
                    obligation_id=obl.id,
                    evidence_id=best.id,
                    satisfied=True,
                    computed_at=now,
                )
                session.add(row)
                rows.append(row)
                obl.status = ObligationStatus.SATISFIED
            elif obl.required:
                failed = any(
                    ev.obligation_id == obl.id and ev.result == EvidenceResult.FAIL
                    for ev in ev_list
                )
                if failed:
                    obl.status = ObligationStatus.FAILED
            await session.flush()
        if rows:
            await append_domain_event(
                session,
                aggregate_type="integration_candidate",
                aggregate_id=integration_candidate_id,
                event_type="coverage.updated",
                payload={"links": len(rows)},
                actor_id=ctx.actor.id,
                correlation_id=ctx.correlation_id,
            )
        return rows
