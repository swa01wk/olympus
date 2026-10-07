"""Allowed evidence types per AC evidence_requirement (Phase 09 §7)."""

from __future__ import annotations

from core.assurance.enums import EvidenceType
from core.domain.enums import EvidenceRequirement

_EXECUTABLE = {
    EvidenceType.UNIT_TEST,
    EvidenceType.INTEGRATION_TEST,
    EvidenceType.API_TEST,
    EvidenceType.E2E_TEST,
    EvidenceType.REGRESSION_TEST,
    EvidenceType.EXTERNAL_CI,
}
_RUNTIME = {
    EvidenceType.RUNTIME_OBSERVATION,
    EvidenceType.API_TEST,
    EvidenceType.E2E_TEST,
}
_REVIEW_EXTRA = {EvidenceType.STATIC_REVIEW}


def allowed_evidence_types(requirement: EvidenceRequirement) -> list[str]:
    if requirement == EvidenceRequirement.EXECUTABLE:
        allowed = _EXECUTABLE
    elif requirement == EvidenceRequirement.RUNTIME:
        allowed = _RUNTIME
    elif requirement == EvidenceRequirement.EXECUTABLE_OR_RUNTIME:
        allowed = _EXECUTABLE | _RUNTIME
    elif requirement == EvidenceRequirement.REVIEW_ALLOWED:
        allowed = _EXECUTABLE | _RUNTIME | _REVIEW_EXTRA
    else:
        allowed = _EXECUTABLE
    return sorted(t.value for t in allowed)


def evidence_satisfies_mandatory(
    evidence_type: str,
    allowed_types: list[str],
    *,
    required: bool,
) -> bool:
    if not required:
        return evidence_type in allowed_types
    if evidence_type == EvidenceType.MODEL_ASSESSMENT.value:
        return False
    return evidence_type in allowed_types
