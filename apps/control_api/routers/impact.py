from __future__ import annotations

import uuid

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.intelligence.impact.engine import ImpactEngine
from core.intelligence.impact.models import ImpactAssessment, ImpactItem, StalenessEvent
from core.state.effects import pin_base_sha
from core.traceability.models import RepositoryIndexPointer
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import command_context, get_db

router = APIRouter(tags=["impact"])


class RunImpactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spec_delta_id: uuid.UUID | None = None
    seed_stable_keys: list[str] | None = None
    index_version_id: uuid.UUID | None = None


@router.post("/delivery-cycles/{cycle_id}/impact-assessments")
async def run_impact_assessment(
    cycle_id: uuid.UUID,
    body: RunImpactRequest,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, str]:
    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None:
        raise HTTPException(404, "Cycle not found")
    index_version_id = body.index_version_id
    if index_version_id is None and cycle.repository_id:
        pointer = await session.get(RepositoryIndexPointer, cycle.repository_id)
        if pointer and pointer.canonical_index_version_id:
            index_version_id = pointer.canonical_index_version_id
    if index_version_id is None:
        raise HTTPException(400, "index_version_id required")
    ia = await ImpactEngine().assess(
        session,
        cycle_id,
        spec_delta_id=body.spec_delta_id,
        seed_stable_keys=body.seed_stable_keys,
        index_version_id=index_version_id,
        ctx=ctx,
    )
    return {"id": str(ia.id), "key": ia.key, "status": ia.status, "content_hash": ia.content_hash}


@router.get("/delivery-cycles/{cycle_id}/impact-assessments/latest")
async def get_latest_impact_assessment(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    ia = (
        await session.execute(
            select(ImpactAssessment)
            .where(ImpactAssessment.delivery_cycle_id == cycle_id)
            .order_by(ImpactAssessment.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if ia is None:
        raise HTTPException(404, "Impact assessment not found")
    return await get_impact_assessment(ia.id, session)


@router.get("/impact-assessments/{ia_id}")
async def get_impact_assessment(
    ia_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    ia = await session.get(ImpactAssessment, ia_id)
    if ia is None:
        raise HTTPException(404, "Impact assessment not found")
    items = (
        await session.execute(select(ImpactItem).where(ImpactItem.impact_assessment_id == ia.id))
    ).scalars()
    grouped: dict[str, list[dict[str, object]]] = {}
    for item in items:
        grouped.setdefault(item.item_type, []).append(
            {
                "ref": item.ref,
                "impact_kind": item.impact_kind,
                "retrieval_source": item.retrieval_source,
                "path": item.path,
                "confidence": item.confidence,
                "selected_for_verification": item.selected_for_verification,
                "rationale": item.rationale,
            }
        )
    return {
        "id": str(ia.id),
        "status": ia.status,
        "architecture_delta_suggested": ia.architecture_delta_suggested,
        "summary": ia.summary,
        "items_by_type": grouped,
    }


@router.get("/specs/{spec_id}/impact")
async def spec_impact_preview(
    spec_id: uuid.UUID,
    delivery_cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, str]:
    from core.product_model.models import FeatureSpec

    spec = await session.get(FeatureSpec, spec_id)
    if spec is None:
        raise HTTPException(404, "Spec not found")
    from_spec_id = spec.supersedes_id
    from core.product_model.specifications.delta import SpecDeltaService

    delta = await SpecDeltaService().compute(
        session,
        from_spec_id=from_spec_id,
        to_spec_id=spec_id,
        delivery_cycle_id=delivery_cycle_id,
        ctx=ctx,
    )
    pointer = None
    cycle = await session.get(DeliveryCycle, delivery_cycle_id)
    if cycle and cycle.repository_id:
        pointer = await session.get(RepositoryIndexPointer, cycle.repository_id)
    if pointer is None or not pointer.canonical_index_version_id:
        raise HTTPException(400, "No canonical index")
    ia = await ImpactEngine().assess(
        session,
        delivery_cycle_id,
        spec_delta_id=delta.id,
        index_version_id=pointer.canonical_index_version_id,
        ctx=ctx,
    )
    return {"impact_assessment_id": str(ia.id), "spec_delta_id": str(delta.id)}


@router.get("/delivery-cycles/{cycle_id}/staleness")
async def list_staleness(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    rows = (
        await session.execute(
            select(StalenessEvent)
            .where(StalenessEvent.delivery_cycle_id == cycle_id)
            .order_by(StalenessEvent.created_at.desc())
        )
    ).scalars()
    return [
        {
            "id": str(r.id),
            "subject_type": r.subject_type,
            "subject_id": str(r.subject_id),
            "from_status": r.from_status,
            "to_status": r.to_status,
            "cause_type": r.cause_type,
            "cause_ref": r.cause_ref,
        }
        for r in rows
    ]


@router.post("/delivery-cycles/{cycle_id}/commands/rebase_cycle")
async def rebase_cycle(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, str]:
    from core.assurance.models import Finding
    from core.domain.enums import TaskStatus
    from core.domain.tasks.models import Task
    from core.integration.enums import FindingStatus

    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None:
        raise HTTPException(404, "Cycle not found")
    open_finding = (
        await session.execute(
            select(Finding).where(
                Finding.delivery_cycle_id == cycle_id,
                Finding.category == "CYCLE_BASE_DIVERGED",
                Finding.status == FindingStatus.OPEN,
            )
        )
    ).scalar_one_or_none()
    if open_finding is None:
        raise HTTPException(409, "CYCLE_BASE_DIVERGED finding not open")
    await pin_base_sha(session, cycle, ctx)
    open_finding.status = FindingStatus.RESOLVED
    tasks = await session.execute(select(Task).where(Task.delivery_cycle_id == cycle_id))
    for task in tasks.scalars():
        if task.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            task.status = TaskStatus.REVALIDATION_REQUIRED
    await session.flush()
    return {"base_sha": cycle.base_sha or ""}
