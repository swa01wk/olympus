"""Assurance delivery-cycle guards."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.enums import GateStatus, GateType
from core.assurance.models import Gate
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import DeliveryCycleType
from core.integration.enums import ICStatus
from core.integration.models import IntegrationCandidate
from core.policy.policy_service import get_cached_policy_content
from core.state.guards import GuardResult


async def required_gates_pass(
    session: AsyncSession,
    cycle: DeliveryCycle,
    _ctx: Any,
) -> GuardResult:
    ic = await session.execute(
        select(IntegrationCandidate)
        .where(
            IntegrationCandidate.delivery_cycle_id == cycle.id,
            IntegrationCandidate.status == ICStatus.READY,
        )
        .order_by(IntegrationCandidate.created_at.desc())
        .limit(1)
    )
    row = ic.scalar_one_or_none()
    if row is None:
        return GuardResult(ok=False, reasons=("IC_NOT_READY",))
    policy = get_cached_policy_content().get("assurance", {})
    required = policy.get(
        "required_gates",
        {
            DeliveryCycleType.GREENFIELD_BUILD.value: [
                GateType.INTEGRATION.value,
                GateType.WARDEN.value,
                GateType.SENTINEL.value,
            ],
        },
    )
    gate_types = required.get(cycle.type.value, required.get("default", []))
    if not gate_types:
        gate_types = [GateType.INTEGRATION.value, GateType.WARDEN.value, GateType.SENTINEL.value]
    gates = await session.execute(
        select(Gate).where(
            Gate.integration_candidate_id == row.id,
            Gate.gate_type.in_(gate_types),
        )
    )
    by_type: dict[str, Gate] = {}
    for gate in sorted(gates.scalars(), key=lambda g: g.created_at):
        if gate.status == GateStatus.SUPERSEDED:
            continue
        by_type[gate.gate_type.value] = gate
    reasons: list[str] = []
    for gt in gate_types:
        gate_row = by_type.get(gt)
        if gate_row is None:
            reasons.append(f"GATE_MISSING:{gt}")
        elif gate_row.status != GateStatus.PASS:
            reasons.append(f"GATE_NOT_PASS:{gt}:{gate_row.status.value}")
    return GuardResult(ok=not reasons, reasons=tuple(reasons))
