from __future__ import annotations

import uuid

from core.domain.enums import ModelOrigin
from core.product_model.models import Capability, Feature, KnowledgeItem, ProductDecomposition
from core.product_model.spec_view import ProductSpecViewService
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import get_db

router = APIRouter(tags=["product_model"])


class CapabilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    key: str
    name: str
    status: str


class FeatureResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    key: str
    name: str
    status: str
    capability_id: uuid.UUID | None
    description: str
    origin: ModelOrigin
    source_refs: list[dict[str, object]]


@router.get("/projects/{project_id}/capabilities", response_model=list[CapabilityResponse])
async def list_capabilities(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[CapabilityResponse]:
    rows = await session.execute(select(Capability).where(Capability.project_id == project_id))
    return [
        CapabilityResponse(id=c.id, key=c.key, name=c.name, status=c.status.value)
        for c in rows.scalars()
    ]


@router.get("/projects/{project_id}/features", response_model=list[FeatureResponse])
async def list_features(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[FeatureResponse]:
    rows = await session.execute(select(Feature).where(Feature.project_id == project_id))
    return [
        FeatureResponse(
            id=f.id,
            key=f.key,
            name=f.name,
            status=f.status.value,
            capability_id=f.capability_id,
            description=f.description,
            origin=f.origin,
            source_refs=list(f.source_refs or []),
        )
        for f in rows.scalars()
    ]


@router.get("/features/{feature_id}", response_model=FeatureResponse)
async def get_feature(
    feature_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> FeatureResponse:
    row = await session.get(Feature, feature_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return FeatureResponse(
        id=row.id,
        key=row.key,
        name=row.name,
        status=row.status.value,
        capability_id=row.capability_id,
        description=row.description,
        origin=row.origin,
        source_refs=list(row.source_refs or []),
    )


@router.get("/projects/{project_id}/product-spec")
async def get_product_spec(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return await ProductSpecViewService().build(session, project_id)


@router.get("/delivery-cycles/{cycle_id}/decompositions")
async def list_decompositions(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    rows = await session.execute(
        select(ProductDecomposition).where(ProductDecomposition.delivery_cycle_id == cycle_id)
    )
    return [
        {
            "id": str(d.id),
            "status": d.status.value,
            "execution_id": str(d.execution_id) if d.execution_id else None,
            "validation_report": d.validation_report,
        }
        for d in rows.scalars()
    ]


@router.get("/decompositions/{decomposition_id}")
async def get_decomposition(
    decomposition_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    row = await session.get(ProductDecomposition, decomposition_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "id": str(row.id),
        "status": row.status.value,
        "validation_report": row.validation_report,
        "product_source_version_id": str(row.product_source_version_id),
    }


@router.get("/delivery-cycles/{cycle_id}/knowledge")
async def list_knowledge(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    rows = await session.execute(
        select(KnowledgeItem).where(KnowledgeItem.delivery_cycle_id == cycle_id)
    )
    return [
        {
            "id": str(k.id),
            "class": k.knowledge_class.value,
            "statement": k.statement,
            "status": k.status.value,
        }
        for k in rows.scalars()
    ]
