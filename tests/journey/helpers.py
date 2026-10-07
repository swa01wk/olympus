"""Journey helpers — API client, wait_for, live LLM proof."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from core.domain.executions.models import Execution
from core.domain.model_calls.models import ModelCall
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession


async def wait_for(
    predicate: Callable[[], Awaitable[bool]],
    *,
    timeout: float = 600.0,
    interval: float = 2.0,
) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if await predicate():
            return
        await asyncio.sleep(interval)
    raise TimeoutError("wait_for timed out")


async def assert_bug_fix_live_llm_proof(
    session: AsyncSession,
    cycle_id: uuid.UUID,
) -> None:
    """Phase 15 journey: at least one live model call; prefer core bug-fix aliases."""
    rows = await session.execute(
        select(ModelCall)
        .join(Execution, ModelCall.execution_id == Execution.id, isouter=True)
        .where(
            or_(
                ModelCall.delivery_cycle_id == cycle_id,
                Execution.delivery_cycle_id == cycle_id,
            )
        )
    )
    live = [
        c
        for c in rows.scalars()
        if c.status == "SUCCEEDED" and c.provider != "fake" and c.provider_request_id is not None
    ]
    assert live, "expected at least one live model call on bug-fix cycle"
    preferred = {
        "product_decomposition",
        "verification_planning",
        "review",
        "planning",
        "implementation",
    }
    assert {c.alias for c in live} & preferred, (
        f"live calls { {c.alias for c in live} } missing bug-fix aliases"
    )


async def assert_live_llm_proof(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    stages: Sequence[str],
) -> None:
    """Assert each stage alias has a succeeded non-fake model call (README §6.3)."""
    for alias in stages:
        rows = await session.execute(
            select(ModelCall)
            .join(Execution, ModelCall.execution_id == Execution.id, isouter=True)
            .where(
                or_(
                    ModelCall.delivery_cycle_id == cycle_id,
                    Execution.delivery_cycle_id == cycle_id,
                ),
                ModelCall.alias == alias,
            )
        )
        calls = list(rows.scalars())
        assert calls, f"no model_calls for alias {alias}"
        ok = any(
            c.status == "SUCCEEDED" and c.provider != "fake" and c.provider_request_id is not None
            for c in calls
        )
        assert ok, f"no live proof for alias {alias}"


class JourneyApiClient:
    """Thin httpx wrapper for journey tests."""

    def __init__(self, client: Any, *, human_token: str | None = None) -> None:
        self._client = client
        self._human_token = human_token

    def _headers(self, human: bool = False) -> dict[str, str]:
        if human and self._human_token:
            return {"Authorization": f"Bearer {self._human_token}"}
        return {}
