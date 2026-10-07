from __future__ import annotations

from core.observability.metrics import metrics_payload
from fastapi import APIRouter, Response

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    return Response(content=metrics_payload(), media_type="text/plain; version=0.0.4")
