"""Bug-fix verification obligations (separate registration from Phase 14)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.enums import EvidenceType, GateType, ObligationReason, ObligationStatus
from core.assurance.models import VerificationObligation
from core.assurance.obligations import register_obligation_source
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import DeliveryCycleType
from core.integration.models import IntegrationCandidate
from core.product_model.defects.models import Defect


async def _defect_reproduction_source(
    session: AsyncSession,
    ic: IntegrationCandidate,
    _ctx: CommandContext,
) -> list[VerificationObligation]:
    cycle = await session.get(DeliveryCycle, ic.delivery_cycle_id)
    if cycle is None or cycle.type != DeliveryCycleType.BUG_FIX:
        return []
    defect = (
        await session.execute(select(Defect).where(Defect.delivery_cycle_id == cycle.id))
    ).scalar_one_or_none()
    if defect is None:
        return []
    return [
        VerificationObligation(
            delivery_cycle_id=cycle.id,
            integration_candidate_id=ic.id,
            gate_type=GateType.REPRODUCTION.value,
            subject_type="DEFECT",
            subject_id=defect.id,
            subject_key=defect.key,
            required=True,
            allowed_evidence_types=[EvidenceType.REPRODUCTION.value],
            reason=ObligationReason.DEFECT_REPRODUCTION,
            source_refs=[{"type": "DEFECT", "id": str(defect.id)}],
            status=ObligationStatus.OPEN,
        )
    ]


async def _defect_regression_source(
    session: AsyncSession,
    ic: IntegrationCandidate,
    _ctx: CommandContext,
) -> list[VerificationObligation]:
    cycle = await session.get(DeliveryCycle, ic.delivery_cycle_id)
    if cycle is None or cycle.type != DeliveryCycleType.BUG_FIX:
        return []
    defect = (
        await session.execute(select(Defect).where(Defect.delivery_cycle_id == cycle.id))
    ).scalar_one_or_none()
    if defect is None:
        return []
    return [
        VerificationObligation(
            delivery_cycle_id=cycle.id,
            integration_candidate_id=ic.id,
            gate_type=GateType.REGRESSION.value,
            subject_type="DEFECT",
            subject_id=defect.id,
            subject_key=defect.key,
            required=True,
            allowed_evidence_types=[EvidenceType.REGRESSION_TEST.value],
            reason=ObligationReason.REGRESSION,
            source_refs=[{"type": "DEFECT", "id": str(defect.id)}],
            status=ObligationStatus.OPEN,
        )
    ]


_bugfix_obligations_registered = False


def register_bugfix_obligation_sources() -> None:
    global _bugfix_obligations_registered
    if _bugfix_obligations_registered:
        return
    register_obligation_source(_defect_reproduction_source)
    register_obligation_source(_defect_regression_source)
    _bugfix_obligations_registered = True


register_bugfix_obligation_sources()
