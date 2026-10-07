"""Connector configuration CRUD (secrets referenced by name only)."""

from __future__ import annotations

import uuid

from core.domain.integrations.models import ConnectorConfig
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.control_api.deps import get_db

router = APIRouter(tags=["connector-configs"])


class ConnectorConfigBody(BaseModel):
    connector: str
    provider: str
    base_url: str | None = None
    secret_ref: str | None = None
    enabled_actions: list[str] = Field(default_factory=list)
    settings: dict[str, object] = Field(default_factory=dict)
    active: bool = True


class ConnectorConfigResponse(ConnectorConfigBody):
    id: uuid.UUID
    project_id: uuid.UUID | None


@router.get(
    "/projects/{project_id}/connector-configs",
    response_model=list[ConnectorConfigResponse],
)
async def list_connector_configs(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[ConnectorConfigResponse]:
    rows = await session.execute(
        select(ConnectorConfig).where(ConnectorConfig.project_id == project_id)
    )
    return [
        ConnectorConfigResponse(
            id=r.id,
            project_id=r.project_id,
            connector=r.connector,
            provider=r.provider,
            base_url=r.base_url,
            secret_ref=r.secret_ref,
            enabled_actions=list(r.enabled_actions or []),
            settings=dict(r.settings or {}),
            active=r.active,
        )
        for r in rows.scalars()
    ]


@router.put(
    "/projects/{project_id}/connector-configs/{connector}",
    response_model=ConnectorConfigResponse,
)
async def upsert_connector_config(
    project_id: uuid.UUID,
    connector: str,
    body: ConnectorConfigBody,
    session: AsyncSession = Depends(get_db),
) -> ConnectorConfigResponse:
    existing = await session.execute(
        select(ConnectorConfig).where(
            ConnectorConfig.project_id == project_id,
            ConnectorConfig.connector == connector,
        )
    )
    row = existing.scalar_one_or_none()
    if row is None:
        row = ConnectorConfig(project_id=project_id, connector=connector, provider=body.provider)
        session.add(row)
    row.provider = body.provider
    row.base_url = body.base_url
    row.secret_ref = body.secret_ref
    row.enabled_actions = body.enabled_actions
    row.settings = body.settings
    row.active = body.active
    await session.flush()
    return ConnectorConfigResponse(
        id=row.id,
        project_id=row.project_id,
        connector=row.connector,
        provider=row.provider,
        base_url=row.base_url,
        secret_ref=row.secret_ref,
        enabled_actions=list(row.enabled_actions or []),
        settings=dict(row.settings or {}),
        active=row.active,
    )
