"""Policy-driven finding severity → blocking map (extended in Phase 09)."""

from __future__ import annotations

from core.policy.policy_service import get_cached_policy_content


class FindingPolicy:
    """Computes whether a finding blocks progress; agents never set blocking directly."""

    def is_blocking(self, severity: str, category: str) -> bool:
        policy = get_cached_policy_content().get("findings", {})
        blocking_severities = set(policy.get("blocking_severities", ["BLOCKER", "MAJOR"]))
        blocking_categories = set(policy.get("blocking_categories", []))
        if severity in blocking_severities:
            return True
        return category in blocking_categories
