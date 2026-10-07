"""Deterministic symptom signature matchers for reproduction evidence."""

from __future__ import annotations

import re
from typing import Any


def classify_junit_failure(cases: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    """Return (outcome_class, failure_detail). outcome_class: ASSERTION | COLLECTION | ERROR."""
    if not cases:
        return "COLLECTION", {"reason": "no test cases"}
    for case in cases:
        if case.get("collection_error"):
            return "COLLECTION", case
        if case.get("error"):
            return "ERROR", case
    failed = [c for c in cases if not c.get("passed")]
    if not failed:
        return "PASS", None
    return "ASSERTION", failed[0]


def match_signature(
    signature: dict[str, Any],
    *,
    http_status: int | None = None,
    exception_type: str | None = None,
    message: str | None = None,
) -> bool:
    kind = signature.get("kind")
    if kind == "http_status":
        expected = signature.get("value")
        if expected is None or http_status is None:
            return False
        return int(expected) == int(http_status)
    if kind == "exception_type":
        expected = str(signature.get("value", ""))
        return exception_type is not None and exception_type == expected
    if kind == "message_regex":
        pattern = str(signature.get("value", ""))
        if not message:
            return False
        return re.search(pattern, message) is not None
    return False


def extract_http_status_from_failure(failure_text: str) -> int | None:
    got = re.search(r"got\s+(4\d{2}|5\d{2})\b", failure_text, flags=re.IGNORECASE)
    if got:
        return int(got.group(1))
    for token in failure_text.replace("'", " ").replace('"', " ").split():
        if token.isdigit() and len(token) == 3:
            code = int(token)
            if 400 <= code < 600:
                return code
    m = re.search(r"\b(4\d{2}|5\d{2})\b", failure_text)
    return int(m.group(1)) if m else None
