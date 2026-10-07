from __future__ import annotations

import pytest
from core.state.guards import GuardRegistry

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_unregistered_guard_fails_closed() -> None:
    registry = GuardRegistry()

    class _Row:
        pass

    result = await registry.evaluate("unknown_guard", None, _Row(), None)  # type: ignore[arg-type]
    assert not result.ok
    assert result.reasons[0].startswith("GUARD_NOT_IMPLEMENTED:")
