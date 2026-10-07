from __future__ import annotations

import uuid

from core.bootstrap.connectors import ensure_connectors_registered
from core.domain.connectors.models import ConnectorActionRecord, ConnectorResultRecord
from core.domain.exceptions import DomainError
from core.integrations.connectors.registry import get_connector_registry
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import get_db

router = APIRouter(tags=["connectors"])


class ConnectorInfo(BaseModel):
    name: str
    ok: bool
    message: str = ""


class ConnectorActionResponse(BaseModel):
    id: uuid.UUID
    connector: str
    action: str
    status: str
    idempotency_key: str
    target_resource: str
    external_ref: str | None
    normalized_result: dict[str, object] | None


@router.get("/connectors", response_model=list[ConnectorInfo])
async def list_connectors() -> list[ConnectorInfo]:
    ensure_connectors_registered()
    registry = get_connector_registry()
    health = await registry.validate_all()
    return [
        ConnectorInfo(name=name, ok=h.ok, message=h.message) for name, h in sorted(health.items())
    ]


@router.post("/connectors/{name}/validate", response_model=ConnectorInfo)
async def validate_connector(name: str) -> ConnectorInfo:
    ensure_connectors_registered()
    registry = get_connector_registry()
    try:
        connector = registry.get(name)
    except KeyError as exc:
        raise DomainError(code="NOT_FOUND", message=f"Unknown connector {name}") from exc
    health = await connector.validate()
    return ConnectorInfo(name=name, ok=health.ok, message=health.message)


@router.get("/connector-actions/{connector_action_id}", response_model=ConnectorActionResponse)
async def get_connector_action(
    connector_action_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ConnectorActionResponse:
    row = await session.get(ConnectorActionRecord, connector_action_id)
    if row is None:
        raise DomainError(code="NOT_FOUND", message="Connector action not found")
    result_row = await session.execute(
        select(ConnectorResultRecord)
        .where(ConnectorResultRecord.connector_action_id == row.id)
        .order_by(ConnectorResultRecord.received_at.desc())
        .limit(1)
    )
    stored = result_row.scalar_one_or_none()
    return ConnectorActionResponse(
        id=row.id,
        connector=row.connector,
        action=row.action,
        status=row.status,
        idempotency_key=row.idempotency_key,
        target_resource=row.target_resource,
        external_ref=row.external_ref,
        normalized_result=stored.normalized_result if stored else None,
    )
