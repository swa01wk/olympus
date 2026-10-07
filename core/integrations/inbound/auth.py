"""Inbound webhook authentication (HMAC-SHA256 + replay window)."""

from __future__ import annotations

import hashlib
import hmac
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.integrations.models import StoredSecret
from core.integrations.connectors.secrets import _fernet
from core.integrations.inbound.models import IntegrationSource

REPLAY_WINDOW_SECONDS = 300


def _parse_github_signature(header: str) -> bytes | None:
    if not header.startswith("sha256="):
        return None
    try:
        return bytes.fromhex(header.removeprefix("sha256="))
    except ValueError:
        return None


def verify_hmac_sha256(secret: str, body: bytes, signature_header: str) -> bool:
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    provided = _parse_github_signature(signature_header)
    if provided is None:
        if signature_header.startswith("sha256="):
            return False
        try:
            provided = bytes.fromhex(signature_header.removeprefix("sha256="))
        except ValueError:
            return False
    return hmac.compare_digest(expected, provided)


def check_replay_window(delivery_timestamp: datetime | None) -> bool:
    if delivery_timestamp is None:
        return True
    now = datetime.now(UTC)
    if delivery_timestamp.tzinfo is None:
        delivery_timestamp = delivery_timestamp.replace(tzinfo=UTC)
    age = abs((now - delivery_timestamp).total_seconds())
    return age <= REPLAY_WINDOW_SECONDS


async def resolve_source_secret(session: AsyncSession, source: IntegrationSource) -> str | None:
    ref = source.secret_ref
    if not ref:
        return None
    if ref.startswith("env:"):
        import os

        var = ref.split(":", 1)[1]
        return os.environ.get(var)
    if ref.startswith("secret:"):
        name = ref.split(":", 1)[1]
        f = _fernet()
        if f is None:
            return None
        row = await session.execute(select(StoredSecret).where(StoredSecret.name == name))
        stored = row.scalar_one_or_none()
        if stored is None:
            return None
        return f.decrypt(stored.ciphertext).decode("utf-8")
    if ref.startswith("file:"):
        from pathlib import Path

        path = Path(ref.split(":", 1)[1]).expanduser()
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
    return None


async def authenticate_hmac_source(
    session: AsyncSession,
    source_type: str,
    source_id: str,
    raw: dict[str, Any],
) -> tuple[bool, str | None]:
    result = await session.execute(
        select(IntegrationSource).where(
            IntegrationSource.source_type == source_type,
            IntegrationSource.name == source_id,
            IntegrationSource.active.is_(True),
        )
    )
    source = result.scalar_one_or_none()
    if source is None or source.auth_kind not in {"HMAC", "HMAC_SHA256"}:
        return False, "SOURCE_NOT_CONFIGURED"
    secret = await resolve_source_secret(session, source)
    if not secret:
        return False, "SECRET_MISSING"
    headers = raw.get("headers") or {}
    sig = headers.get("X-Hub-Signature-256") or headers.get("X-Gitea-Signature") or ""
    body = raw.get("raw_body")
    if body is None:
        import json

        body = json.dumps(raw.get("json_body") or {}, separators=(",", ":")).encode("utf-8")
    elif isinstance(body, str):
        body = body.encode("utf-8")
    if not verify_hmac_sha256(secret, body, str(sig)):
        secondary = None
        if source.secondary_secret_ref and source.secondary_valid_until:
            now = datetime.now(UTC).replace(tzinfo=None)
            until = source.secondary_valid_until
            if until.tzinfo:
                until = until.replace(tzinfo=None)
            if until >= now:
                secondary = await resolve_source_secret(
                    session,
                    IntegrationSource(
                        source_type=source.source_type,
                        name=source.name,
                        auth_kind=source.auth_kind,
                        secret_ref=source.secondary_secret_ref,
                    ),
                )
        if not secondary or not verify_hmac_sha256(secondary, body, str(sig)):
            return False, "INVALID_SIGNATURE"
    ts_raw = headers.get("X-GitHub-Delivery") or headers.get("X-Gitea-Delivery")
    delivered = raw.get("delivered_at")
    if delivered is not None:
        if isinstance(delivered, str):
            delivered = datetime.fromisoformat(delivered.replace("Z", "+00:00"))
        if not check_replay_window(delivered):
            return False, "REPLAY_WINDOW"
    elif ts_raw:
        pass
    else:
        if raw.get("timestamp") is not None:
            ts = float(raw["timestamp"])
            if abs(time.time() - ts) > REPLAY_WINDOW_SECONDS:
                return False, "REPLAY_WINDOW"
    return True, None
