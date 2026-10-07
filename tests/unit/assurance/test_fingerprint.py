from __future__ import annotations

import pytest
from core.assurance.findings import compute_fingerprint

pytestmark = pytest.mark.unit


def test_fingerprint_stable() -> None:
    a = compute_fingerprint(
        "WARDEN",
        "SECURITY",
        [{"file_path": "src/a.py", "line_start": 10}],
    )
    b = compute_fingerprint(
        "WARDEN",
        "SECURITY",
        [{"file_path": "src/a.py", "line_start": 10}],
    )
    assert a == b
    c = compute_fingerprint(
        "WARDEN",
        "CORRECTNESS",
        [{"file_path": "src/a.py", "line_start": 10}],
    )
    assert a != c
