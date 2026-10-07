from __future__ import annotations

import uuid

from core.intelligence.brownfield.models import (
    ObservedBehavior,
    RecoveryProposal,
    RepositoryDiscovery,
)
from core.product_model.models import KnowledgeItem
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import get_db

router = APIRouter(tags=["brownfield"])


class DiscoveryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    repository_id: uuid.UUID
    delivery_cycle_id: uuid.UUID
    commit_sha: str
    content: dict[str, object]
    content_hash: str


class ObservedBehaviorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    key: str
    kind: str
    description: str
    commit_sha: str
    confidence: float
    passed: bool | None


class RecoveryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposals: list[dict[str, object]]


@router.get("/delivery-cycles/{cycle_id}/discovery", response_model=DiscoveryResponse)
async def get_discovery(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> DiscoveryResponse:
    row = (
        await session.execute(
            select(RepositoryDiscovery)
            .where(RepositoryDiscovery.delivery_cycle_id == cycle_id)
            .order_by(RepositoryDiscovery.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="discovery not found")
    return DiscoveryResponse(
        id=row.id,
        repository_id=row.repository_id,
        delivery_cycle_id=row.delivery_cycle_id,
        commit_sha=row.commit_sha,
        content=row.content,
        content_hash=row.content_hash,
    )


@router.get(
    "/delivery-cycles/{cycle_id}/observed-behaviors",
    response_model=list[ObservedBehaviorResponse],
)
async def list_observed_behaviors(
    cycle_id: uuid.UUID,
    kind: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> list[ObservedBehaviorResponse]:
    q = select(ObservedBehavior).where(ObservedBehavior.delivery_cycle_id == cycle_id)
    if kind:
        from core.intelligence.brownfield.enums import ObservedBehaviorKind

        q = q.where(ObservedBehavior.kind == ObservedBehaviorKind(kind))
    rows = (await session.execute(q.order_by(ObservedBehavior.key))).scalars().all()
    return [
        ObservedBehaviorResponse(
            id=r.id,
            key=r.key,
            kind=r.kind.value,
            description=r.description,
            commit_sha=r.commit_sha,
            confidence=r.confidence,
            passed=r.passed,
        )
        for r in rows
    ]


@router.get("/delivery-cycles/{cycle_id}/knowledge")
async def list_cycle_knowledge(
    cycle_id: uuid.UUID,
    class_: str = Query(alias="class"),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    rows = (
        (
            await session.execute(
                select(KnowledgeItem).where(
                    KnowledgeItem.delivery_cycle_id == cycle_id,
                    KnowledgeItem.knowledge_class == class_,
                )
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": str(r.id),
            "class": r.knowledge_class.value,
            "statement": r.statement,
            "provenance": r.provenance,
            "confidence": r.confidence,
            "blocking": r.blocking,
        }
        for r in rows
    ]


@router.get("/delivery-cycles/{cycle_id}/recovery", response_model=RecoveryResponse)
async def get_recovery(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> RecoveryResponse:
    rows = (
        (
            await session.execute(
                select(RecoveryProposal)
                .where(RecoveryProposal.delivery_cycle_id == cycle_id)
                .order_by(RecoveryProposal.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return RecoveryResponse(
        proposals=[
            {
                "id": str(r.id),
                "status": r.status.value,
                "validation_report": r.validation_report,
                "context_manifest_hash": r.context_manifest_hash,
            }
            for r in rows
        ]
    )
