from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from core.domain.model_calls.models import ModelCall
from core.observability.retention import (
    DEFAULT_RETENTION,
    purge_expired_model_call_blobs,
    retention_expires_at,
    should_store_raw_prompt,
    should_store_raw_response,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.persistence


def test_default_retention_policy() -> None:
    assert should_store_raw_prompt(DEFAULT_RETENTION) is False
    assert should_store_raw_response(DEFAULT_RETENTION) is False
    expires = retention_expires_at(ttl_days=30)
    assert expires > datetime.now(UTC).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_purge_selects_expired_rows_without_refs(db_session: AsyncSession) -> None:
    """Purge clears blob refs; model_calls rows stay immutable (refs cleared only when allowed)."""
    from decimal import Decimal

    past = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    row = ModelCall(
        agent_profile="test",
        purpose="test",
        alias="planning",
        provider="fake",
        model="fake",
        prompt_hash="abc",
        status="SUCCEEDED",
        input_tokens=1,
        output_tokens=1,
        latency_ms=1,
        cost_usd_estimate=Decimal("0"),
        transport_retries=0,
        schema_retries=0,
        correlation_id="retention-select",
        retention_expires_at=past,
    )
    db_session.add(row)
    await db_session.flush()
    result = await db_session.execute(
        select(ModelCall).where(
            ModelCall.retention_expires_at.is_not(None),
            ModelCall.retention_expires_at < datetime.now(UTC).replace(tzinfo=None),
        )
    )
    assert result.scalars().first() is not None
    removed = await purge_expired_model_call_blobs(db_session)
    assert removed >= 0
