"""Phase 16 integration command handlers."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.repositories.sync import RepositorySyncService


async def handle_record_repository_event(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    repository_id = uuid.UUID(payload["repository_id"])
    inbound_event_id = payload.get("inbound_event_id")
    ie_id = uuid.UUID(inbound_event_id) if inbound_event_id else None
    event = await RepositorySyncService().sync(
        session,
        repository_id,
        ctx,
        inbound_event_id=ie_id,
        before_sha=payload.get("before_sha"),
        after_sha=payload.get("after_sha"),
        ref=payload.get("ref"),
    )
    return {
        "repository_event_id": str(event.id) if event else None,
        "classification": event.classification if event else None,
    }


async def handle_attach_remote(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from core.domain.enums import RepositoryProvider
    from core.repositories.remote import RemoteRepositoryService

    repo = await RemoteRepositoryService().attach_remote(
        session,
        uuid.UUID(payload["repository_id"]),
        RepositoryProvider(payload["provider"]),
        payload["remote_url"],
        payload.get("credential_ref", "none:"),
        ctx,
    )
    return {"repository_id": str(repo.id), "remote_url": repo.remote_url}
