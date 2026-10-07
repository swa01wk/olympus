from __future__ import annotations

import pytest
from core.security.redaction import redact_string
from core.security.secret_scan import contains_secret

pytestmark = pytest.mark.unit


def test_redact_openai_key() -> None:
    raw = "token sk-abcdefghijklmnopqrstuvwxyz1234567890 end"
    assert "[REDACTED]" in redact_string(raw)
    assert "sk-" not in redact_string(raw)


def test_secret_scan_ghp() -> None:
    assert contains_secret("ghp_1234567890123456789012345678901234")
