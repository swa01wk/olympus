"""Deterministic action policy decisions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from core.domain.enums import ActorKind


@dataclass(frozen=True)
class PolicyDecision:
    decision: str
    rule_ids: list[str]
    reasons: list[str]
    policy_version_id: str | None
    requires_approval: bool = False


def _load_actions_policy() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "config" / "policy" / "default.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    actions = raw.get("actions", {})
    return actions if isinstance(actions, dict) else {}


def evaluate_action_policy(
    *,
    resource: str,
    action: str,
    tool: str,
    agent_profile: str | None,
    actor_kind: ActorKind,
    params: dict[str, Any],
    policy_version_id: str | None,
    risk_tier: str | None = None,
) -> PolicyDecision:
    cfg = _load_actions_policy()
    reasons: list[str] = []
    rule_ids: list[str] = []
    for rule in cfg.get("deny", []):
        match = rule.get("match", {})
        if (
            match.get("resource") == resource
            and match.get("action") == action
            and match.get("actor_kind") == actor_kind.value
        ):
            rule_ids.append("deny.actor")
            reasons.append(f"denied: {resource}.{action} for {actor_kind.value}")
        if match.get("resource") == resource and match.get("action") == "*":
            prefix = match.get("agent_profile_prefix", "")
            if agent_profile and agent_profile.startswith(prefix):
                rule_ids.append("deny.agent_profile")
                reasons.append(f"denied: {resource} for profile {agent_profile}")
        if match.get("protected_ref") and resource == "git" and action == "commit":
            branch = str(params.get("branch", ""))
            if branch in ("main", "master") or branch.startswith("release/"):
                rule_ids.append("deny.protected_ref")
                reasons.append(f"denied: commit to protected branch {branch}")
    if resource == "repository" and action == "merge_candidate" and actor_kind == ActorKind.AGENT:
        rule_ids.append("deny.merge_candidate")
        reasons.append("agents cannot merge_candidate")

    if reasons:
        return PolicyDecision(
            decision="DENY",
            rule_ids=rule_ids,
            reasons=reasons,
            policy_version_id=policy_version_id,
        )

    requires = (
        resource == "repository" and action == "merge_candidate" and risk_tier in {"R2", "R3"}
    )
    if requires:
        return PolicyDecision(
            decision="REQUIRE_APPROVAL",
            rule_ids=["risk.approval"],
            reasons=["action requires approval"],
            policy_version_id=policy_version_id,
            requires_approval=True,
        )
    return PolicyDecision(
        decision="ALLOW",
        rule_ids=[],
        reasons=[],
        policy_version_id=policy_version_id,
    )
