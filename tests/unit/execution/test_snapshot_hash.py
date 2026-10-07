from __future__ import annotations

import uuid

import pytest
from core.domain.canonical_json import sha256_hex
from core.domain.executions.schemas import SnapshotContent
from core.domain.task_contracts.schemas import VersionedRef

pytestmark = pytest.mark.unit


def test_snapshot_hash_stable_under_key_order() -> None:
    ref_a = VersionedRef(ref_type="ARTIFACT", ref_id=uuid.uuid4())
    ref_b = VersionedRef(ref_type="ARTIFACT", ref_id=uuid.uuid4())
    base: dict[str, object] = {
        "task": {"id": "t1", "key": "T-1", "work_type": "ANALYSIS", "origin": "CONTROL_PLANE"},
        "task_contract": {"id": "c1", "key": "v1", "version": 1, "content_hash": "abc"},
        "base_commit": None,
        "base_resolution": {"policy": "NONE", "inputs": {}},
        "artifact_versions": [ref_b, ref_a],
        "policy_version": {"id": "p1", "version": 1, "content_hash": "pol"},
        "risk_tier": "STANDARD",
    }
    h1 = sha256_hex(SnapshotContent.model_validate(base).model_dump(mode="json"))
    reordered = {
        "risk_tier": base["risk_tier"],
        "policy_version": base["policy_version"],
        "artifact_versions": base["artifact_versions"],
        "base_resolution": base["base_resolution"],
        "base_commit": base["base_commit"],
        "task_contract": base["task_contract"],
        "task": base["task"],
    }
    h2 = sha256_hex(SnapshotContent.model_validate(reordered).model_dump(mode="json"))
    assert h1 == h2
