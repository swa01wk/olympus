"""Regression stage gate finalization."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.enums import EvidenceResult, EvidenceType, GateStatus, GateType
from core.assurance.gates import FINALIZER_ACTOR
from core.assurance.models import Evidence, Gate
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.integration.enums import ICStatus
from core.integration.models import IntegrationCandidate
from core.product_model.defects.models import Defect


async def finalize_regression_gates(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    ctx: CommandContext,
) -> None:
    del ctx
    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None:
        return
    ic = (
        await session.execute(
            select(IntegrationCandidate)
            .where(
                IntegrationCandidate.delivery_cycle_id == cycle_id,
                IntegrationCandidate.status == ICStatus.READY,
            )
            .order_by(IntegrationCandidate.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if ic is None:
        return
    defect = (
        await session.execute(select(Defect).where(Defect.delivery_cycle_id == cycle_id))
    ).scalar_one_or_none()
    if defect is None:
        return

    for gt, ev_type in (
        (GateType.REPRODUCTION, EvidenceType.REPRODUCTION),
        (GateType.REGRESSION, EvidenceType.REGRESSION_TEST),
    ):
        ev = (
            await session.execute(
                select(Evidence)
                .where(
                    Evidence.integration_candidate_id == ic.id,
                    Evidence.subject_id == defect.id,
                    Evidence.evidence_type == ev_type,
                    Evidence.result == EvidenceResult.PASS,
                )
                .order_by(Evidence.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if ev is None:
            continue
        existing = (
            await session.execute(
                select(Gate)
                .where(
                    Gate.integration_candidate_id == ic.id,
                    Gate.gate_type == gt,
                    Gate.status != GateStatus.SUPERSEDED,
                )
                .order_by(Gate.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        now = datetime.now(UTC)
        if existing is None:
            session.add(
                Gate(
                    integration_candidate_id=ic.id,
                    gate_type=gt,
                    status=GateStatus.PASS,
                    summary=f"Bug-fix {gt.value} gate",
                    finalized_by=FINALIZER_ACTOR,
                    finalized_at=now,
                )
            )
        elif existing.status == GateStatus.PASS:
            continue
        elif existing.status == GateStatus.FAIL:
            existing.status = GateStatus.SUPERSEDED
            session.add(
                Gate(
                    integration_candidate_id=ic.id,
                    gate_type=gt,
                    status=GateStatus.PASS,
                    summary=f"Bug-fix {gt.value} gate",
                    finalized_by=FINALIZER_ACTOR,
                    finalized_at=now,
                )
            )
        else:
            existing.status = GateStatus.PASS
            existing.finalized_by = FINALIZER_ACTOR
            existing.finalized_at = now

    if defect.status != "FIXED":
        defect.status = "FIXED"
    await session.flush()
