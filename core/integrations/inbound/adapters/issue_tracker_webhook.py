"""Issue tracker webhook → change request / defect intake."""

from __future__ import annotations

import uuid
from typing import Any

from core.commands.context import CommandContext
from core.integrations.inbound.auth import authenticate_hmac_source
from core.integrations.inbound.envelope import InboundEventEnvelope
from core.integrations.inbound.storage import sha256_text
from sqlalchemy.ext.asyncio import AsyncSession


class IssueTrackerWebhookAdapter:
    source_type = "issue_tracker_webhook"

    async def authenticate(
        self,
        session: AsyncSession,
        raw: dict[str, Any],
        ctx: CommandContext | None,
    ) -> tuple[bool, str | None]:
        del ctx
        return await authenticate_hmac_source(
            session, self.source_type, str(raw.get("source_id", "default")), raw
        )

    async def validate(self, session: AsyncSession, raw: dict[str, Any]) -> tuple[bool, str | None]:
        del session
        body = raw.get("json_body") or raw
        issue = body.get("issue") or body
        if not issue.get("title"):
            return False, "issue.title required"
        if not raw.get("project_id"):
            return False, "project_id required"
        return True, None

    async def normalize(self, session: AsyncSession, raw: dict[str, Any]) -> InboundEventEnvelope:
        del session
        body = raw.get("json_body") or raw
        issue = body.get("issue") or body
        labels = {lbl.get("name") for lbl in issue.get("labels", []) if isinstance(lbl, dict)}
        event_id = str(raw.get("event_id") or issue.get("number") or uuid.uuid4())
        normalized = {
            "title": issue.get("title"),
            "body": issue.get("body") or "",
            "labels": list(labels),
            "external_ref": (
                f"{issue.get('repository', {}).get('full_name', 'repo')}#{issue.get('number')}"
            ),
            "updated_at": issue.get("updated_at"),
            "content_hash": sha256_text(str(issue.get("body") or "")),
        }
        raw["_normalized"] = normalized
        return InboundEventEnvelope(
            source_type=self.source_type,
            source_id=str(raw.get("source_id", "default")),
            event_id=event_id,
            project_id=str(raw["project_id"]),
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
        labels = set(normalized.get("labels") or [])
        cmd = "intake_defect" if "olympus:defect" in labels else "intake_change_request"
        payload = {
            "project_id": envelope.project_id,
            "title": normalized["title"],
            "description": normalized.get("body") or normalized["title"],
            "source_type": "ISSUE_TRACKER",
            "external_ref": normalized.get("external_ref"),
        }
        return (cmd, "project", envelope.project_id, payload)
