from __future__ import annotations

import uuid
from typing import Any

from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind
from core.integrations.inbound.envelope import InboundEventEnvelope
from core.integrations.inbound.storage import sha256_text
from sqlalchemy.ext.asyncio import AsyncSession


class ChangeRequestApiAdapter:
    source_type = "change_request_api"

    async def authenticate(
        self,
        session: AsyncSession,
        raw: dict[str, Any],
        ctx: CommandContext | None,
    ) -> tuple[bool, str | None]:
        if ctx is None:
            return False, "UNAUTHENTICATED"
        actor = await session.get(Actor, ctx.actor.id)
        if actor is None:
            return False, "UNAUTHENTICATED"
        if actor.kind not in {ActorKind.HUMAN, ActorKind.INTEGRATION, ActorKind.SYSTEM}:
            return False, "UNAUTHORIZED"
        return True, None

    async def validate(self, session: AsyncSession, raw: dict[str, Any]) -> tuple[bool, str | None]:
        del session
        body = raw.get("json_body") or raw
        if not body.get("title") or not body.get("description"):
            return False, "title and description required"
        if not raw.get("project_id"):
            return False, "project_id required"
        return True, None

    async def normalize(self, session: AsyncSession, raw: dict[str, Any]) -> InboundEventEnvelope:
        del session
        project_id = str(raw["project_id"])
        body = raw.get("json_body") or raw
        title = str(body["title"])
        description = str(body["description"])
        external_ref = body.get("external_ref")
        event_id = str(raw.get("event_id") or raw.get("idempotency_key") or uuid.uuid4())
        source_id = str(raw.get("source_id") or project_id)
        normalized = {
            "title": title,
            "description": description,
            "external_ref": str(external_ref) if external_ref else None,
            "content_hash": sha256_text(description),
        }
        raw["_normalized"] = normalized
        return InboundEventEnvelope(
            source_type=self.source_type,
            source_id=source_id,
            event_id=event_id,
            project_id=project_id,
            payload={"content_hash": normalized["content_hash"]},
        )

    async def to_command(
        self,
        session: AsyncSession,
        envelope: InboundEventEnvelope,
        normalized: dict[str, Any],
    ) -> tuple[str, str, str, dict[str, Any]]:
        del session
        assert envelope.project_id is not None
        payload = {
            "project_id": envelope.project_id,
            "title": normalized["title"],
            "description": normalized["description"],
            "source_type": self.source_type,
            "external_ref": normalized.get("external_ref"),
        }
        return ("intake_change_request", "project", envelope.project_id, payload)
