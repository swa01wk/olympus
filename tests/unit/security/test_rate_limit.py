from __future__ import annotations

import pytest
from core.security.rate_limit import check_rate_limit

pytestmark = [pytest.mark.unit, pytest.mark.persistence]


@pytest.mark.asyncio
async def test_rate_limit_window(db_session) -> None:
    allowed1, _ = await check_rate_limit(db_session, key="k1", limit=2, window_seconds=60)
    allowed2, count2 = await check_rate_limit(db_session, key="k1", limit=2, window_seconds=60)
    allowed3, count3 = await check_rate_limit(db_session, key="k1", limit=2, window_seconds=60)
    assert allowed1 and allowed2
    assert not allowed3
    assert count3 == 3
