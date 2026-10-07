from __future__ import annotations

import uuid

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.exceptions import DomainError, Unauthorized
from core.release.eligibility import ReleaseEligibilityService
from core.release.models import (
    DeliveryOutcome,
    Release,
    ReleaseEligibilityEvaluation,
    ReleaseManifest,
)
from core.release.service import ReleaseService
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import command_context, get_db

router = APIRouter(tags=["releases"])


class ConditionResponse(BaseModel):
    name: str
    ok: bool
    reasons: list[str]
    inputs_hash: str


class EligibilityResponse(BaseModel):
    id: uuid.UUID
    delivery_cycle_id: uuid.UUID
    eligible: bool
    conditions: list[ConditionResponse]
    integration_candidate_id: uuid.UUID | None


class ReleaseResponse(BaseModel):
    id: uuid.UUID
    key: str
    project_id: uuid.UUID
    delivery_cycle_id: uuid.UUID
    integrated_sha: str
    status: str
    manifest_id: uuid.UUID | None
    tag: str | None


class ManifestResponse(BaseModel):
    content: dict[str, object]
    content_hash: str


class OutcomeResponse(BaseModel):
    delivery_cycle_id: uuid.UUID
    result: str
    content: dict[str, object]


@router.get(
    "/delivery-cycles/{cycle_id}/release-eligibility",
    response_model=EligibilityResponse,
)
async def get_release_eligibility(
    cycle_id: uuid.UUID,
    recompute: bool = Query(default=False),
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> EligibilityResponse:
    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail="Cycle not found")
    row: ReleaseEligibilityEvaluation | None
    if recompute:
        row = await ReleaseEligibilityService().recompute_and_persist(session, cycle_id, ctx)
    else:
        release = await session.execute(
            select(Release)
            .where(Release.delivery_cycle_id == cycle_id)
            .order_by(Release.created_at.desc())
            .limit(1)
        )
        rel = release.scalar_one_or_none()
        if rel and rel.latest_eligibility_id:
            row = await session.get(ReleaseEligibilityEvaluation, rel.latest_eligibility_id)
        else:
            row = (
                await session.execute(
                    select(ReleaseEligibilityEvaluation)
                    .where(ReleaseEligibilityEvaluation.delivery_cycle_id == cycle_id)
                    .order_by(ReleaseEligibilityEvaluation.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
        if row is None:
            row = await ReleaseEligibilityService().recompute_and_persist(session, cycle_id, ctx)
    assert row is not None
    return _eligibility_resp(row)


@router.post("/delivery-cycles/{cycle_id}/release", response_model=ReleaseResponse, status_code=201)
async def create_release(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> ReleaseResponse:
    try:
        release = await ReleaseService().create_release(session, cycle_id, ctx)
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _release_resp(release)


@router.get("/releases/{release_id}", response_model=ReleaseResponse)
async def get_release(
    release_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ReleaseResponse:
    release = await session.get(Release, release_id)
    if release is None:
        raise HTTPException(status_code=404, detail="Release not found")
    return _release_resp(release)


@router.get("/projects/{project_id}/releases", response_model=list[ReleaseResponse])
async def list_releases(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[ReleaseResponse]:
    rows = await session.execute(
        select(Release).where(Release.project_id == project_id).order_by(Release.created_at.desc())
    )
    return [_release_resp(r) for r in rows.scalars()]


@router.get("/releases/{release_id}/manifest", response_model=ManifestResponse)
async def get_manifest(
    release_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ManifestResponse:
    release = await session.get(Release, release_id)
    if release is None or release.manifest_id is None:
        raise HTTPException(status_code=404, detail="Manifest not found")
    manifest = await session.get(ReleaseManifest, release.manifest_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail="Manifest not found")
    return ManifestResponse(content=manifest.content, content_hash=manifest.content_hash)


@router.post("/releases/{release_id}/approve", response_model=ReleaseResponse)
async def approve_release(
    release_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> ReleaseResponse:
    try:
        release = await ReleaseService().approve_release(session, release_id, ctx)
    except Unauthorized:
        raise
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _release_resp(release)


@router.post("/releases/{release_id}/execute")
async def execute_release(
    release_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    ctx: CommandContext = Depends(command_context),
) -> dict[str, str]:
    try:
        execution_id = await ReleaseService().execute_release(session, release_id, ctx)
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return {"execution_id": str(execution_id)}


@router.get("/delivery-cycles/{cycle_id}/outcome", response_model=OutcomeResponse)
async def get_outcome(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> OutcomeResponse:
    row = (
        await session.execute(
            select(DeliveryOutcome).where(DeliveryOutcome.delivery_cycle_id == cycle_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Outcome not found")
    return OutcomeResponse(
        delivery_cycle_id=row.delivery_cycle_id,
        result=row.result,
        content=row.content,
    )


def _release_resp(release: Release) -> ReleaseResponse:
    return ReleaseResponse(
        id=release.id,
        key=release.key,
        project_id=release.project_id,
        delivery_cycle_id=release.delivery_cycle_id,
        integrated_sha=release.integrated_sha,
        status=release.status.value,
        manifest_id=release.manifest_id,
        tag=release.tag,
    )


def _eligibility_resp(row: ReleaseEligibilityEvaluation) -> EligibilityResponse:
    return EligibilityResponse(
        id=row.id,
        delivery_cycle_id=row.delivery_cycle_id,
        eligible=row.eligible,
        integration_candidate_id=row.integration_candidate_id,
        conditions=[
            ConditionResponse(
                name=c["name"],
                ok=c["ok"],
                reasons=list(c.get("reasons") or []),
                inputs_hash=c.get("inputs_hash", ""),
            )
            for c in (row.conditions or [])
        ],
    )
