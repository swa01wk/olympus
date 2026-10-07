from __future__ import annotations

import uuid

from core.commands.bus import CommandBus
from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import SpecKind
from core.intelligence.brownfield.models import RecoveredSpecEvidence
from core.product_model.models import FeatureSpec
from core.product_model.schemas import FeatureSpecBody
from core.product_model.specifications.scope import ScopeService
from core.product_model.specifications.service import FeatureSpecService
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.command_dispatch import dispatch
from apps.control_api.deps import command_context, get_command_bus, get_db

router = APIRouter(tags=["specs"])


class SpecSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    version: int
    status: str
    lineage_key: str


class CreateSpecRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: FeatureSpecBody


class ScopeApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_spec_ids: list[uuid.UUID]


@router.get("/features/{feature_id}/specs", response_model=list[SpecSummary])
async def list_specs(
    feature_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[SpecSummary]:
    rows = await session.execute(
        select(FeatureSpec)
        .where(FeatureSpec.feature_id == feature_id)
        .order_by(FeatureSpec.version)
    )
    return [
        SpecSummary(id=s.id, version=s.version, status=s.status.value, lineage_key=s.lineage_key)
        for s in rows.scalars()
    ]


@router.get("/specs/{spec_id}")
async def get_spec(
    spec_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    spec, reqs, stories, acs = await FeatureSpecService().get_with_children(session, spec_id)
    evidence_rows = (
        (
            await session.execute(
                select(RecoveredSpecEvidence).where(
                    RecoveredSpecEvidence.feature_spec_id == spec.id
                )
            )
        )
        .scalars()
        .all()
    )
    out: dict[str, object] = {
        "id": str(spec.id),
        "version": spec.version,
        "status": spec.status.value,
        "spec_kind": spec.spec_kind.value,
        "body": spec.body,
        "requirements": [
            {"id": str(r.id), "lineage_key": r.lineage_key, "statement": r.statement} for r in reqs
        ],
        "user_stories": [
            {"id": str(s.id), "lineage_key": s.lineage_key, "actor": s.actor, "goal": s.goal}
            for s in stories
        ],
        "acceptance_criteria": [
            {
                "id": str(a.id),
                "lineage_key": a.lineage_key,
                "statement": a.statement,
                "mandatory": a.mandatory,
                "evidence_requirement": a.evidence_requirement.value,
            }
            for a in acs
        ],
    }
    if spec.spec_kind == SpecKind.RECOVERED:
        out["confidence"] = spec.confidence
        out["claimed_confidence"] = spec.claimed_confidence
        out["uncertainty_count"] = spec.uncertainty_count
        out["recovered_evidence"] = [
            {
                "element_type": e.element_type,
                "element_key": e.element_key,
                "support_type": e.support_type,
                "support_ref": e.support_ref,
                "strength": e.strength,
            }
            for e in evidence_rows
        ]
    return out


@router.post("/features/{feature_id}/specs")
async def create_spec_draft(
    feature_id: uuid.UUID,
    body: CreateSpecRequest,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, str]:
    spec = await FeatureSpecService().create_draft_version(session, feature_id, body.body, ctx)
    return {"spec_id": str(spec.id), "version": str(spec.version)}


@router.post("/delivery-cycles/{cycle_id}/scope/approval-request")
async def scope_approval_request(
    cycle_id: uuid.UUID,
    body: ScopeApprovalRequest,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
    bus: CommandBus = Depends(get_command_bus),
) -> dict[str, object]:
    result = await dispatch(
        session,
        bus,
        name="request_scope_approval",
        target_type="delivery_cycle",
        target_id=str(cycle_id),
        payload={
            "delivery_cycle_id": str(cycle_id),
            "feature_spec_ids": [str(i) for i in body.feature_spec_ids],
        },
        ctx=ctx,
    )
    return result.data


@router.post("/specs/{spec_id}/approve")
async def approve_spec(
    spec_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, str]:
    spec = await session.get(FeatureSpec, spec_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Not found")
    cycle = await session.execute(
        select(DeliveryCycle)
        .where(DeliveryCycle.project_id == spec.project_id)
        .order_by(DeliveryCycle.created_at.desc())
        .limit(1)
    )
    cycle_row = cycle.scalar_one_or_none()
    if cycle_row is None:
        raise HTTPException(status_code=422, detail="No delivery cycle")
    approval_id = await ScopeService().approve_single_spec(
        session,
        spec_id,
        spec.project_id,
        cycle_row.id,
        ctx,
    )
    return {"approval_id": str(approval_id)}
