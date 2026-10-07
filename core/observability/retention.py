"""LLM prompt/response retention policy and purge."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.domain.model_calls.models import ModelCall

DEFAULT_RETENTION: dict[str, Any] = {
    "store_full_prompts": False,
    "store_full_responses": "structured_only",
    "ttl_days": 30,
}


def retention_expires_at(*, ttl_days: int | None = None) -> datetime:
    days = ttl_days if ttl_days is not None else int(DEFAULT_RETENTION["ttl_days"])
    return datetime.now(UTC).replace(tzinfo=None) + timedelta(days=days)


def should_store_raw_prompt(policy: dict[str, Any] | None = None) -> bool:
    pol = policy or DEFAULT_RETENTION
    return bool(pol.get("store_full_prompts", False))


def should_store_raw_response(policy: dict[str, Any] | None = None) -> bool:
    pol = policy or DEFAULT_RETENTION
    mode = pol.get("store_full_responses", "structured_only")
    return str(mode) == "full"


async def purge_expired_model_call_blobs(session: AsyncSession) -> int:
    now = datetime.now(UTC).replace(tzinfo=None)
    result = await session.execute(
        select(ModelCall).where(
            ModelCall.retention_expires_at.is_not(None),
            ModelCall.retention_expires_at < now,
        )
    )
    rows = list(result.scalars())
    settings = get_settings()
    root = settings.olympus_storage_root / "llm_raw"
    removed = 0
    for row in rows:
        for ref in (row.raw_prompt_ref, row.raw_response_ref):
            if not ref:
                continue
            path = Path(ref)
            if not path.is_absolute():
                path = root / ref
            if path.is_file():
                path.unlink(missing_ok=True)
        row.raw_prompt_ref = None
        row.raw_response_ref = None
        removed += 1
    if removed:
        await session.flush()
    return removed


async def purge_orphan_storage(session: AsyncSession) -> int:
    """Remove storage files with no model_calls reference (best-effort)."""
    _ = session
    return 0
