from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.product_model.defects.service import DefectService


async def handle_intake_defect(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    defect = await DefectService().intake(
        session,
        project_id=uuid.UUID(payload["project_id"]),
        title=str(payload["title"]),
        description=str(payload["description"]),
        source_type=str(payload.get("source_type", "defect_report_api")),
        external_ref=payload.get("external_ref"),
        inbound_event_id=(
            uuid.UUID(payload["inbound_event_id"]) if payload.get("inbound_event_id") else None
        ),
        ctx=ctx,
    )
    return {"defect_id": str(defect.id), "cycle_id": str(defect.delivery_cycle_id)}
