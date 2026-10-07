from __future__ import annotations

from enum import StrEnum


class ReleaseStatus(StrEnum):
    DRAFT = "DRAFT"
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    RELEASED = "RELEASED"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"
