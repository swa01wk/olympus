"""Git provider push webhook → repository sync."""

from __future__ import annotations

import uuid
from typing import Any

from core.commands.context import CommandContext
from core.domain.repositories.models import Repository
from core.integrations.inbound.auth import authenticate_hmac_source
from core.integrations.inbound.envelope import InboundEventEnvelope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class GitProviderWebhookAdapter:
    source_type = "git_provider_webhook"

    async def authenticate(
        self,
        session: AsyncSession,
        raw: dict[str, Any],
        ctx: CommandContext | None,
    ) -> tuple[bool, str | None]:
        del ctx
        source_id = str(raw.get("source_id", "default"))
        return await authenticate_hmac_source(session, self.source_type, source_id, raw)

    async def validate(self, session: AsyncSession, raw: dict[str, Any]) -> tuple[bool, str | None]:
        del session
        body = raw.get("json_body") or raw
        if not body.get("repository") and not raw.get("repository_id"):
            return False, "repository required"
        return True, None

    async def normalize(self, session: AsyncSession, raw: dict[str, Any]) -> InboundEventEnvelope:
        body = raw.get("json_body") or raw
        project_id = raw.get("project_id")
        event_id = str(
            raw.get("event_id")
            or (raw.get("headers") or {}).get("X-Gitea-Delivery")
            or (raw.get("headers") or {}).get("X-GitHub-Delivery")
            or uuid.uuid4()
        )
        ref = str(body.get("ref", ""))
        before = body.get("before")
        after = body.get("after") or body.get("head_commit", {}).get("id")
        normalized = {
            "ref": ref,
            "before_sha": before,
            "after_sha": after,
            "repository_id": raw.get("repository_id") or body.get("repository_id"),
        }
        raw["_normalized"] = normalized
        return InboundEventEnvelope(
            source_type=self.source_type,
            source_id=str(raw.get("source_id", "default")),
            event_id=event_id,
            project_id=str(project_id) if project_id else None,
            payload=normalized,
        )

    async def to_command(
        self,
        session: AsyncSession,
        envelope: InboundEventEnvelope,
        normalized: dict[str, Any],
    ) -> tuple[str, str, str, dict[str, Any]]:
        repository_id = normalized.get("repository_id") or envelope.payload.get("repository_id")
        if not repository_id:
            remote_url = (envelope.payload.get("repository") or {}).get("html_url")
            if remote_url:
                row = await session.execute(
                    select(Repository).where(
                        Repository.remote_url.contains(remote_url.split("//")[-1])
                    )
                )
                repo = row.scalar_one_or_none()
                if repo:
                    repository_id = str(repo.id)
        if not repository_id:
            raise ValueError("repository_id could not be resolved")
        payload = {
            "repository_id": repository_id,
            "ref": normalized.get("ref"),
            "before_sha": normalized.get("before_sha"),
            "after_sha": normalized.get("after_sha"),
        }
        return ("record_repository_event", "repository", repository_id, payload)
