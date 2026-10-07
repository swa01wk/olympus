from __future__ import annotations

import pytest
from core.observability.retention import (
    DEFAULT_RETENTION,
    should_store_raw_prompt,
    should_store_raw_response,
)

pytestmark = pytest.mark.unit


def test_llm_retention_defaults() -> None:
    assert should_store_raw_prompt(DEFAULT_RETENTION) is False
    assert should_store_raw_response(DEFAULT_RETENTION) is False
