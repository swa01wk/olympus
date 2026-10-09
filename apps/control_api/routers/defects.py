from __future__ import annotations

import uuid

from core.commands.bus import CommandBus
from core.commands.context import CommandContext
from core.integrations.inbound.service import InboundService
from core.product_model.defects.service import DefectService
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import command_context, get_command_bus, get_db

router = APIRouter(tags=["defects"])


class DefectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    external_ref: str | None = None


class ProceedUnreproducedBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1)


class RejectDefectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = None


@router.post("/projects/{project_id}/defects")
async def create_defect(
    project_id: uuid.UUID,
    body: DefectCreate,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
    bus: CommandBus = Depends(get_command_bus),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, object]:
    inbound = InboundService(bus)
    raw = {
        "project_id": str(project_id),
        "json_body": body.model_dump(),
        "idempotency_key": idempotency_key or str(uuid.uuid4()),
        "event_id": idempotency_key or str(uuid.uuid4()),
    }
    return await inbound.receive(session, "defect_report_api", raw, ctx)


@router.get("/projects/{project_id}/defects")
async def list_defects(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    from core.product_model.defects.models import Defect

    rows = (await session.execute(select(Defect).where(Defect.project_id == project_id))).scalars()
    return [
        {
            "id": str(r.id),
            "key": r.key,
            "status": r.status,
            "delivery_cycle_id": str(r.delivery_cycle_id) if r.delivery_cycle_id else None,
            "title": r.title,
            "severity": r.severity,
        }
        for r in rows
    ]


@router.get("/defects/{defect_id}")
async def get_defect(
    defect_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    defect = await DefectService().get(session, defect_id)
    return {
        "id": str(defect.id),
        "key": defect.key,
        "status": defect.status,
        "title": defect.title,
        "description": defect.description,
        "triage": defect.triage,
        "linked_feature_ids": defect.linked_feature_ids,
        "expected_ac_ids": defect.expected_ac_ids,
        "affected_sha": defect.affected_sha,
        "delivery_cycle_id": str(defect.delivery_cycle_id) if defect.delivery_cycle_id else None,
    }


@router.get("/defects/{defect_id}/expected-behavior-review")
async def get_expected_behavior_review(
    defect_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    from core.domain.exceptions import DomainError
    from fastapi import HTTPException

    try:
        return await DefectService().expected_behavior_review_payload(session, defect_id)
    except DomainError as exc:
        if exc.code == "NOT_FOUND":
            raise HTTPException(status_code=404, detail=exc.message) from exc
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.get("/expected-behavior-resolutions/{resolution_id}/review")
async def get_expected_behavior_review_by_resolution(
    resolution_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    from core.domain.exceptions import DomainError
    from core.product_model.defects.models import ExpectedBehaviorResolution
    from fastapi import HTTPException

    row = await session.get(ExpectedBehaviorResolution, resolution_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Resolution not found")
    try:
        return await DefectService().resolution_review_payload(session, row)
    except DomainError as exc:
        if exc.code == "NOT_FOUND":
            raise HTTPException(status_code=404, detail=exc.message) from exc
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.get("/defects/{defect_id}/reproductions")
async def list_defect_reproductions(
    defect_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    svc = DefectService()
    await svc.get(session, defect_id)
    rows = await svc.list_reproductions(session, defect_id)
    return [
        {
            "id": str(r.id),
            "phase": r.phase,
            "commit_sha": r.commit_sha,
            "artifact_id": str(r.artifact_id),
            "artifact_hash": r.artifact_hash,
            "outcome": r.outcome,
            "signature_matched": r.signature_matched,
            "evidence_id": str(r.evidence_id) if r.evidence_id else None,
        }
        for r in rows
    ]


@router.get("/defects/{defect_id}/trace")
async def get_defect_trace(
    defect_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = DefectService()
    await svc.get(session, defect_id)
    trace = await svc.latest_trace_correlation(session, defect_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace correlation not found")
    return {
        "id": str(trace.id),
        "reproduction_id": str(trace.reproduction_id),
        "entry_route_key": trace.entry_route_key,
        "traceback_stable_keys": trace.traceback_stable_keys,
        "executed_stable_keys": trace.executed_stable_keys,
        "candidates": trace.candidates,
    }


@router.get("/defects/{defect_id}/root-cause")
async def get_defect_root_cause(
    defect_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    svc = DefectService()
    await svc.get(session, defect_id)
    rca = await svc.latest_root_cause(session, defect_id)
    if rca is None:
        raise HTTPException(status_code=404, detail="Root cause analysis not found")
    return {
        "id": str(rca.id),
        "knowledge_class": rca.knowledge_class,
        "faulty_stable_keys": rca.faulty_stable_keys,
        "explanation": rca.explanation,
        "confidence": rca.confidence,
        "fix_outline": rca.fix_outline,
        "impact_assessment_id": str(rca.impact_assessment_id) if rca.impact_assessment_id else None,
        "status": rca.status,
    }


@router.post("/defects/{defect_id}/proceed-unreproduced")
async def proceed_unreproduced(
    defect_id: uuid.UUID,
    body: ProceedUnreproducedBody,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, object]:
    approval = await DefectService().proceed_unreproduced(
        session, defect_id, ctx, reason=body.reason
    )
    return {"approval_id": str(approval.id), "status": approval.status.value}


@router.post("/defects/{defect_id}/reject")
async def reject_defect(
    defect_id: uuid.UUID,
    body: RejectDefectBody,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, object]:
    defect = await DefectService().reject_defect(session, defect_id, ctx, reason=body.reason)
    return {"id": str(defect.id), "status": defect.status}


@router.post("/knowledge-items/{knowledge_item_id}/create-defect")
async def create_defect_from_knowledge_item(
    knowledge_item_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, object]:
    defect = await DefectService().create_from_suggestion(session, knowledge_item_id, ctx)
    return {
        "id": str(defect.id),
        "key": defect.key,
        "delivery_cycle_id": str(defect.delivery_cycle_id) if defect.delivery_cycle_id else None,
    }
