"""Scheduled LLM retention purge (scheduler worker tick)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.observability.logging import get_logger
from core.observability.retention import purge_expired_model_call_blobs

logger = get_logger(__name__)


async def run_retention_purge(session: AsyncSession) -> int:
    removed = await purge_expired_model_call_blobs(session)
    if removed:
        logger.info("retention.purge", removed=removed)
    return removed
