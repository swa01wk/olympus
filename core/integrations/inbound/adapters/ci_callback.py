"""CI run.completed callback → EXTERNAL_CI evidence."""

from __future__ import annotations

import uuid
from typing import Any

from core.commands.context import CommandContext
from core.integrations.inbound.auth import authenticate_hmac_source
from core.integrations.inbound.envelope import InboundEventEnvelope
from sqlalchemy.ext.asyncio import AsyncSession


class CiCallbackAdapter:
    source_type = "ci_callback"

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
        if not body.get("sha") or not body.get("run_id"):
            return False, "sha and run_id required"
        return True, None

    async def normalize(self, session: AsyncSession, raw: dict[str, Any]) -> InboundEventEnvelope:
        del session
        body = raw.get("json_body") or raw
        event_id = str(body.get("run_id") or uuid.uuid4())
        normalized = {
            "run_id": str(body["run_id"]),
            "sha": str(body["sha"]),
            "status": body.get("status", "PASSED"),
            "suite": body.get("suite", "default"),
            "junit_ref": body.get("junit_ref"),
            "correlation_id": body.get("correlation_id"),
        }
        raw["_normalized"] = normalized
        return InboundEventEnvelope(
            source_type=self.source_type,
            source_id=str(raw.get("source_id", "default")),
            event_id=event_id,
            project_id=str(raw["project_id"]) if raw.get("project_id") else None,
            payload=normalized,
        )

    async def to_command(
        self,
        session: AsyncSession,
        envelope: InboundEventEnvelope,
        normalized: dict[str, Any],
    ) -> tuple[str, str, str, dict[str, Any]]:
        del session, envelope
        return (
            "ingest_external_ci_result",
            "project",
            str(normalized.get("project_id") or ""),
            normalized,
        )
