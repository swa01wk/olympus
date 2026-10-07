from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.exceptions import DomainError
from core.product_model.decomposition import DecompositionOrchestrator
from core.product_model.models import ProductSource
from core.product_model.sources.service import ProductSourceService
from core.product_model.specifications.scope import ScopeService


async def handle_ingest_product_source(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    inbound_id = payload.get("inbound_event_id")
    return await ProductSourceService().ingest(
        session,
        project_id=uuid.UUID(payload["project_id"]),
        lineage_key=payload["lineage_key"],
        source_type=payload["source_type"],
        title=payload["title"],
        mime_type=payload["mime_type"],
        content_hash=payload["content_hash"],
        raw_storage_ref=payload["raw_storage_ref"],
        text=payload["text"],
        ctx=ctx,
        delivery_cycle_id=uuid.UUID(payload["delivery_cycle_id"])
        if payload.get("delivery_cycle_id")
        else None,
        inbound_event_id=uuid.UUID(inbound_id) if inbound_id else None,
    )


async def handle_decompose_source(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    source = await session.get(ProductSource, uuid.UUID(payload["source_version_id"]))
    if source is None:
        raise DomainError(code="NOT_FOUND", message="Product source not found")
    cycle_id = uuid.UUID(payload["delivery_cycle_id"])
    return await DecompositionOrchestrator().start_decomposition(
        session, source=source, delivery_cycle_id=cycle_id, ctx=ctx
    )


async def handle_request_scope_approval(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    cycle_id = uuid.UUID(payload["delivery_cycle_id"])
    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None:
        raise DomainError(code="NOT_FOUND", message="Delivery cycle not found")
    spec_ids = [uuid.UUID(s) for s in payload["feature_spec_ids"]]
    scope_set, approval_id = await ScopeService().request_scope_approval(
        session,
        cycle_id,
        spec_ids,
        cycle.project_id,
        ctx,
    )
    return {
        "scope_set_id": str(scope_set.id),
        "approval_id": str(approval_id),
        "content_hash": scope_set.content_hash,
    }
