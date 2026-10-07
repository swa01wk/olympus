"""Network egress policy for agent tools."""

from __future__ import annotations


class EgressPolicyViolation(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def assert_egress_allowed(*, tool: str, network_requested: bool, allow_connectors: bool) -> None:
    if not network_requested:
        return
    if tool.startswith("connector.") and allow_connectors:
        return
    raise EgressPolicyViolation("network egress denied for agent tools")
