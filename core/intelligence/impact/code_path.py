"""Deterministic code-path resolution for bug-fix root cause."""

from __future__ import annotations

from dataclasses import dataclass

from core.policy.policy_service import get_cached_policy_content


@dataclass(frozen=True)
class CodePathCandidate:
    stable_key: str
    evidence_basis: str
    path: list[str]


class CodePathResolver:
    def resolve(
        self,
        *,
        entry_route_key: str | None,
        traceback_stable_keys: list[str],
        executed_stable_keys: list[str],
        graph_reachable: list[str] | None = None,
    ) -> list[CodePathCandidate]:
        policy = get_cached_policy_content().get("bugfix", {})
        max_depth = int(policy.get("graph_reach_depth", 4))
        del max_depth  # reserved for graph traversal expansion
        graph_reachable = graph_reachable or []
        seen: set[str] = set()
        out: list[CodePathCandidate] = []

        def add(key: str, basis: str, path: list[str]) -> None:
            if key in seen:
                return
            seen.add(key)
            out.append(CodePathCandidate(stable_key=key, evidence_basis=basis, path=path))

        for key in traceback_stable_keys:
            add(key, "TRACEBACK", [k for k in [entry_route_key, key] if k])
        for key in executed_stable_keys:
            if key in traceback_stable_keys:
                continue
            add(key, "EXECUTED", [k for k in [entry_route_key, key] if k])
        for key in graph_reachable:
            if key in seen:
                continue
            add(key, "GRAPH_ONLY", [k for k in [entry_route_key, key] if k])
        return out
