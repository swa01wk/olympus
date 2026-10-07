from __future__ import annotations

import uuid
from typing import Any

from core.traceability.lineage.factory import build_lineage_service
from core.traceability.lineage.service import LineageGraph
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import get_db

router = APIRouter(tags=["lineage"])


class LineageGraphResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


def _serialize(graph: LineageGraph) -> LineageGraphResponse:
    return LineageGraphResponse(
        nodes=[n.__dict__ for n in graph.nodes],
        edges=[e.__dict__ for e in graph.edges],
    )


@router.get("/code/entities/{entity_id}/lineage")
async def entity_lineage(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> LineageGraphResponse:
    graph = await build_lineage_service().reverse(session, entity_id)
    return _serialize(graph)


@router.get("/features/{feature_id}/lineage")
async def feature_lineage(
    feature_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> LineageGraphResponse:
    graph = await build_lineage_service().forward(session, "FEATURE", feature_id)
    return _serialize(graph)
