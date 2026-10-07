from __future__ import annotations

import pytest
from core.assurance.evidence_rules import allowed_evidence_types
from core.domain.enums import EvidenceRequirement

pytestmark = pytest.mark.unit


def test_mandatory_ac_executable_allowed_types() -> None:
    types = allowed_evidence_types(EvidenceRequirement.EXECUTABLE)
    assert "UNIT_TEST" in types
    assert "MODEL_ASSESSMENT" not in types


def test_review_allowed_includes_static_review() -> None:
    types = allowed_evidence_types(EvidenceRequirement.REVIEW_ALLOWED)
    assert "STATIC_REVIEW" in types
