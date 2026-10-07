from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.product_model.changes.service import ChangeRequestService


async def handle_intake_change_request(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    inbound_id = payload.get("inbound_event_id")
    source_type = str(payload.get("source_type", "change_request_api"))
    cr = await ChangeRequestService().intake(
        session,
        project_id=uuid.UUID(payload["project_id"]),
        title=str(payload["title"]),
        description=str(payload["description"]),
        source_type=source_type,
        external_ref=payload.get("external_ref"),
        inbound_event_id=uuid.UUID(inbound_id) if inbound_id else None,
        ctx=ctx,
    )
    external_ref = payload.get("external_ref")
    if external_ref and source_type == "ISSUE_TRACKER":
        from core.domain.integrations.models import ExternalLink

        session.add(
            ExternalLink(
                entity_type="change_request",
                entity_id=cr.id,
                provider="gitea",
                external_type="issue",
                external_id=str(external_ref),
                url=None,
            )
        )
        await session.flush()
    return {
        "change_request_id": str(cr.id),
        "delivery_cycle_id": str(cr.delivery_cycle_id),
        "key": cr.key,
        "status": cr.status,
    }
