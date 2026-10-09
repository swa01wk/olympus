from __future__ import annotations

import uuid

from core.commands.context import CommandContext
from core.intelligence.baselines.models import BaselineSet, BehavioralBaseline
from core.intelligence.baselines.provisional import known_gaps_for_baseline
from core.intelligence.baselines.service import BaselineService
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import command_context, get_db

router = APIRouter(tags=["baselines"])


class BaselineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lineage_key: str
    version: int
    status: str
    source: str
    check_kind: str
    check_ref: str
    established_sha: str
    feature_spec_id: uuid.UUID | None
    provisional: bool = False
    provisional_known_gaps: list[str] = Field(default_factory=list)
    latest_evidence_id: uuid.UUID | None = None


class BaselineSetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    commit_sha: str
    content_hash: str
    delivery_cycle_id: uuid.UUID


async def _baseline_response(session: AsyncSession, row: BehavioralBaseline) -> BaselineResponse:
    provisional = bool(row.provisional)
    return BaselineResponse(
        id=row.id,
        lineage_key=row.lineage_key,
        version=row.version,
        status=row.status.value,
        source=row.source.value,
        check_kind=row.check_kind.value,
        check_ref=row.check_ref,
        established_sha=row.established_sha,
        feature_spec_id=row.feature_spec_id,
        provisional=provisional,
        provisional_known_gaps=(await known_gaps_for_baseline(session, row) if provisional else []),
        latest_evidence_id=row.established_evidence_id,
    )


@router.get("/projects/{project_id}/baselines", response_model=list[BaselineResponse])
async def list_baselines(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[BaselineResponse]:
    rows = (
        (
            await session.execute(
                select(BehavioralBaseline)
                .where(BehavioralBaseline.project_id == project_id)
                .order_by(BehavioralBaseline.lineage_key)
            )
        )
        .scalars()
        .all()
    )
    return [await _baseline_response(session, row) for row in rows]


@router.get("/baselines/{baseline_id}", response_model=BaselineResponse)
async def get_baseline(
    baseline_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> BaselineResponse:
    row = await session.get(BehavioralBaseline, baseline_id)
    if row is None:
        raise HTTPException(status_code=404, detail="baseline not found")
    return await _baseline_response(session, row)


@router.post("/baselines/{baseline_id}/activate", response_model=BaselineResponse)
async def activate_baseline(
    baseline_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> BaselineResponse:
    row = await BaselineService().activate_human(session, baseline_id, ctx)
    return await _baseline_response(session, row)


@router.get("/projects/{project_id}/baseline-sets", response_model=list[BaselineSetResponse])
async def list_baseline_sets(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[BaselineSetResponse]:
    rows = (
        (
            await session.execute(
                select(BaselineSet)
                .where(BaselineSet.project_id == project_id)
                .order_by(BaselineSet.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [
        BaselineSetResponse(
            id=r.id,
            key=r.key,
            commit_sha=r.commit_sha,
            content_hash=r.content_hash,
            delivery_cycle_id=r.delivery_cycle_id,
        )
        for r in rows
    ]


@router.get("/baseline-sets/{baseline_set_id}", response_model=BaselineSetResponse)
async def get_baseline_set(
    baseline_set_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> BaselineSetResponse:
    row = await session.get(BaselineSet, baseline_set_id)
    if row is None:
        raise HTTPException(status_code=404, detail="baseline set not found")
    return BaselineSetResponse(
        id=row.id,
        key=row.key,
        commit_sha=row.commit_sha,
        content_hash=row.content_hash,
        delivery_cycle_id=row.delivery_cycle_id,
    )
