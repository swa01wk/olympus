from __future__ import annotations

import pytest
from core.runtime.profiles.diagnostic import DiagnosticSummary
from core.runtime.structured_output import validate_or_feedback, validation_feedback_message

pytestmark = pytest.mark.unit


def test_validate_success() -> None:
    parsed, errors = validate_or_feedback(
        DiagnosticSummary,
        {"title": "t", "bullet_points": ["a"], "word_count_estimate": 3},
        None,
    )
    assert parsed is not None
    assert errors == []


def test_validate_failure_feedback() -> None:
    _, errors = validate_or_feedback(
        DiagnosticSummary,
        {"title": "t", "bullet_points": [], "word_count_estimate": 3},
        None,
    )
    assert errors
    msg = validation_feedback_message(errors)
    assert "schema validation" in msg.lower()
