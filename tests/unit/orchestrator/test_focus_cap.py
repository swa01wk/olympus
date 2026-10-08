from __future__ import annotations

import pytest
from core.orchestrator.focus import apply_focus_cap

pytestmark = pytest.mark.unit


def test_apply_focus_cap_truncates_large_sources() -> None:
    payload = {
        "type": "architecture",
        "id": "a",
        "key": "ARCH",
        "version": 1,
        "status": "PROPOSED",
        "content_hash": "h",
        "body": {"summary": "x"},
        "sources": "x" * 30_000,
    }
    capped = apply_focus_cap(payload)
    assert capped.get("truncated") is True
    assert len(str(capped.get("sources", ""))) < 30_000
