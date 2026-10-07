from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from core.domain.canonical_json import canonical_json, sha256_hex

pytestmark = pytest.mark.unit


def test_canonical_json_key_order() -> None:
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_canonical_json_unicode() -> None:
    raw = canonical_json({"msg": "café"})
    assert "caf" in raw
    assert sha256_hex({"msg": "café"}) == sha256_hex({"msg": "café"})


def test_canonical_json_uuid_datetime() -> None:
    uid = uuid.UUID("00000000-0000-0000-0000-000000000001")
    dt = datetime(2026, 1, 1, tzinfo=UTC)
    h1 = sha256_hex({"id": uid, "at": dt})
    h2 = sha256_hex({"at": dt, "id": uid})
    assert h1 == h2
