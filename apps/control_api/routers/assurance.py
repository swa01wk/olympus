from __future__ import annotations

import uuid
from typing import Any

from core.assurance.findings import FindingService
from core.assurance.gates import GateFinalizerService
from core.assurance.models import (
    AcceptanceCoverage,
    Evidence,
    Gate,
    VerificationObligation,
    VerificationPlanRow,
    WardenReviewRecord,
)
from core.assurance.orchestrator import AssuranceOrchestrator
from core.assurance.remediation import RemediationService
from core.commands.context import CommandContext
from core.domain.enums import ActorKind
from core.domain.exceptions import Unauthorized
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import command_context, get_db

router = APIRouter(tags=["assurance"])


class GateResponse(BaseModel):
    id: uuid.UUID
    key: str
    gate_type: str
    status: str
    reasons: list[Any]
    recommendation: dict[str, Any] | None
    inputs_hash: str | None


@router.get("/integration-candidates/{ic_id}/gates")
async def list_gates(
    ic_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[GateResponse]:
    rows = await session.execute(select(Gate).where(Gate.integration_candidate_id == ic_id))
    return [
        GateResponse(
            id=g.id,
            key=g.key,
            gate_type=g.gate_type.value,
            status=g.status.value,
            reasons=list(g.reasons or []),
            recommendation=g.recommendation,
            inputs_hash=g.inputs_hash,
        )
        for g in rows.scalars()
    ]


@router.get("/gates/{gate_id}")
async def get_gate(
    gate_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> GateResponse:
    g = await session.get(Gate, gate_id)
    if g is None:
        raise HTTPException(status_code=404, detail="Not found")
    return GateResponse(
        id=g.id,
        key=g.key,
        gate_type=g.gate_type.value,
        status=g.status.value,
        reasons=list(g.reasons or []),
        recommendation=g.recommendation,
        inputs_hash=g.inputs_hash,
    )


@router.post("/gates/{gate_id}/finalize")
async def finalize_gate(
    gate_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> GateResponse:
    if ctx.actor.kind == ActorKind.AGENT:
        raise HTTPException(status_code=403, detail="Agents cannot finalize gates")
    try:
        gate = await GateFinalizerService().finalize(session, gate_id, ctx)
    except Unauthorized:
        raise HTTPException(status_code=403, detail="Forbidden") from None
    return GateResponse(
        id=gate.id,
        key=gate.key,
        gate_type=gate.gate_type.value,
        status=gate.status.value,
        reasons=list(gate.reasons or []),
        recommendation=gate.recommendation,
        inputs_hash=gate.inputs_hash,
    )


@router.get("/integration-candidates/{ic_id}/obligations")
async def list_obligations(
    ic_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    rows = await session.execute(
        select(VerificationObligation).where(
            VerificationObligation.integration_candidate_id == ic_id
        )
    )
    return [
        {
            "id": str(o.id),
            "subject_key": o.subject_key,
            "required": o.required,
            "reason": o.reason.value,
            "source_refs": o.source_refs,
            "status": o.status.value,
            "allowed_evidence_types": o.allowed_evidence_types,
        }
        for o in rows.scalars()
    ]


@router.get("/delivery-cycles/{cycle_id}/evidence")
async def list_evidence(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    rows = await session.execute(select(Evidence).where(Evidence.delivery_cycle_id == cycle_id))
    return [
        {
            "id": str(e.id),
            "key": e.key,
            "commit_sha": e.commit_sha,
            "evidence_type": e.evidence_type.value,
            "result": e.result.value,
            "producer": e.producer.value,
        }
        for e in rows.scalars()
    ]


@router.get("/evidence/{evidence_id}")
async def get_evidence(
    evidence_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    e = await session.get(Evidence, evidence_id)
    if e is None:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "id": str(e.id),
        "key": e.key,
        "commit_sha": e.commit_sha,
        "details": e.details,
    }


@router.get("/delivery-cycles/{cycle_id}/coverage")
async def list_coverage(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    obligations = await session.execute(
        select(VerificationObligation).where(VerificationObligation.delivery_cycle_id == cycle_id)
    )
    obl_map = {o.id: o for o in obligations.scalars()}
    if not obl_map:
        return []
    coverage = await session.execute(
        select(AcceptanceCoverage).where(AcceptanceCoverage.obligation_id.in_(obl_map.keys()))
    )
    out: list[dict[str, Any]] = []
    for row in coverage.scalars():
        obl = obl_map.get(row.obligation_id)
        out.append(
            {
                "obligation_key": obl.subject_key if obl else None,
                "evidence_id": str(row.evidence_id),
                "satisfied": row.satisfied,
            }
        )
    return out


@router.post("/integration-candidates/{ic_id}/warden")
async def schedule_warden(
    ic_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, str]:
    result = await AssuranceOrchestrator().on_integration_ready(session, ic_id, ctx)
    return {"status": "scheduled", "detail": str(result)}


@router.post("/integration-candidates/{ic_id}/sentinel")
async def schedule_sentinel(
    ic_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, str]:
    result = await AssuranceOrchestrator().on_integration_ready(session, ic_id, ctx)
    return {"status": "scheduled", "detail": str(result)}


@router.post("/findings/{finding_id}/remediate")
async def remediate_finding(
    finding_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, str]:
    task_id = await RemediationService().remediate_finding(session, finding_id, ctx)
    return {"task_id": str(task_id)}


@router.post("/findings/{finding_id}/waive")
async def waive_finding(
    finding_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, str]:
    from core.assurance.models import Finding
    from core.domain.delivery_cycles.models import DeliveryCycle

    finding = await session.get(Finding, finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="Not found")
    cycle = await session.get(DeliveryCycle, finding.delivery_cycle_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail="Cycle not found")
    approval_id = await FindingService().request_waiver(session, finding_id, cycle.project_id, ctx)
    return {"approval_id": str(approval_id)}


@router.get("/verification-plans/{plan_id}")
async def get_verification_plan(
    plan_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = await session.get(VerificationPlanRow, plan_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "id": str(row.id),
        "status": row.status.value,
        "validation_report": row.validation_report,
    }


@router.get("/reviews/{review_id}")
async def get_review(
    review_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = await session.get(WardenReviewRecord, review_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "id": str(row.id),
        "recommendation": row.recommendation,
        "summary": row.summary,
    }
