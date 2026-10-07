from __future__ import annotations

from enum import StrEnum


class ICStatus(StrEnum):
    CREATED = "CREATED"
    INTEGRATING = "INTEGRATING"
    VALIDATING = "VALIDATING"
    READY = "READY"
    CONFLICT = "CONFLICT"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


class FindingSource(StrEnum):
    INTEGRATION = "INTEGRATION"
    WARDEN = "WARDEN"
    SENTINEL = "SENTINEL"
    SYSTEM = "SYSTEM"
    READINESS = "READINESS"
    LINEAGE = "LINEAGE"


class FindingSeverity(StrEnum):
    BLOCKER = "BLOCKER"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    INFO = "INFO"


class FindingStatus(StrEnum):
    OPEN = "OPEN"
    IN_REMEDIATION = "IN_REMEDIATION"
    RESOLVED = "RESOLVED"
    WAIVED = "WAIVED"
    SUPERSEDED = "SUPERSEDED"


class EntityChangeKind(StrEnum):
    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"


class SpecCodeLinkRelation(StrEnum):
    IMPLEMENTS = "IMPLEMENTS"
    VERIFIES = "VERIFIES"


class SpecCodeLinkOrigin(StrEnum):
    GENERATED_LINEAGE = "GENERATED_LINEAGE"
    DISCOVERED = "DISCOVERED"
    HUMAN_CONFIRMED = "HUMAN_CONFIRMED"


class SpecCodeLinkStatus(StrEnum):
    ACTIVE = "ACTIVE"
    STALE = "STALE"
    RETIRED = "RETIRED"
    SUPERSEDED = "SUPERSEDED"
