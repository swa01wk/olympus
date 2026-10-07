from __future__ import annotations

import pytest
from core.domain.exceptions import DomainError
from core.security.snapshot_gate import assert_no_secrets_in_payload

pytestmark = pytest.mark.security


def test_snapshot_rejects_openai_key() -> None:
    with pytest.raises(DomainError, match="Secret pattern"):
        assert_no_secrets_in_payload(
            {"notes": "use sk-abcdefghijklmnopqrstuvwxyz1234567890"},
            context="snapshot",
        )
