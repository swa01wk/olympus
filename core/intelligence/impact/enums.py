from __future__ import annotations

from enum import StrEnum


class SpecDeltaStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class ImpactAssessmentStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    STALE = "STALE"
    SUPERSEDED = "SUPERSEDED"


class ImpactSeedKind(StrEnum):
    SPEC_DELTA = "SPEC_DELTA"
    DEFECT_ROOT_CAUSE = "DEFECT_ROOT_CAUSE"
    MANUAL = "MANUAL"


class ImpactItemType(StrEnum):
    CODE_ENTITY = "CODE_ENTITY"
    TEST = "TEST"
    BASELINE = "BASELINE"
    CONTRACT = "CONTRACT"
    SPEC = "SPEC"


class ImpactKind(StrEnum):
    DIRECT = "DIRECT"
    TRANSITIVE = "TRANSITIVE"
    CANDIDATE = "CANDIDATE"
    SEMANTIC_CANDIDATE = "SEMANTIC_CANDIDATE"


class ImpactRetrievalSource(StrEnum):
    STRUCTURAL = "STRUCTURAL"
    LEXICAL = "LEXICAL"
    SEMANTIC = "SEMANTIC"


class BaselineImpactFloor(StrEnum):
    IMPACTED_ONLY = "IMPACTED_ONLY"
    IMPACTED_PLUS_SMOKE = "IMPACTED_PLUS_SMOKE"
    ALL = "ALL"
