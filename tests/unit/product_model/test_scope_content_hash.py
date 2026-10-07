from __future__ import annotations

import uuid

import pytest


@pytest.mark.unit
def test_scope_set_hash_stable_for_same_specs() -> None:
    spec_fingerprints = sorted(
        [
            {"id": str(uuid.uuid4()), "version": 1, "hash": "aaa"},
            {"id": str(uuid.uuid4()), "version": 1, "hash": "bbb"},
        ],
        key=lambda item: item["id"],
    )
    import json

    from core.domain.canonical_json import sha256_hex

    payload = json.dumps(spec_fingerprints, sort_keys=True, separators=(",", ":"))
    h1 = sha256_hex(payload)
    h2 = sha256_hex(payload)
    assert h1 == h2
