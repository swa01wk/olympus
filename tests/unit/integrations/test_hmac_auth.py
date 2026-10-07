from datetime import UTC, datetime, timedelta

import pytest
from core.integrations.inbound.auth import (
    check_replay_window,
    verify_hmac_sha256,
)

pytestmark = pytest.mark.integration


def test_hmac_valid() -> None:
    body = b'{"ref":"refs/heads/main"}'
    import hashlib
    import hmac

    sig = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert verify_hmac_sha256("secret", body, f"sha256={sig}")


def test_hmac_invalid() -> None:
    assert not verify_hmac_sha256("secret", b"x", "sha256=00")


def test_replay_window_expired() -> None:
    old = datetime.now(UTC) - timedelta(minutes=10)
    assert not check_replay_window(old)


def test_replay_window_fresh() -> None:
    assert check_replay_window(datetime.now(UTC))
