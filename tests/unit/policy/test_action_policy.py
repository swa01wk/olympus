import pytest
from core.domain.enums import ActorKind
from core.policy.action_policy import evaluate_action_policy

pytestmark = pytest.mark.unit


def test_deny_git_commit_to_main() -> None:
    decision = evaluate_action_policy(
        resource="git",
        action="commit",
        tool="git.commit",
        agent_profile="forge.implementation",
        actor_kind=ActorKind.AGENT,
        params={"branch": "main"},
        policy_version_id=None,
    )
    assert decision.decision == "DENY"
    assert "protected branch" in decision.reasons[0]


def test_deny_release_actions_for_forge() -> None:
    decision = evaluate_action_policy(
        resource="release",
        action="publish",
        tool="release.publish",
        agent_profile="forge.implementation",
        actor_kind=ActorKind.AGENT,
        params={},
        policy_version_id=None,
    )
    assert decision.decision == "DENY"


def test_deny_merge_candidate_for_agent() -> None:
    decision = evaluate_action_policy(
        resource="repository",
        action="merge_candidate",
        tool="repository.merge_candidate",
        agent_profile="forge.implementation",
        actor_kind=ActorKind.AGENT,
        params={},
        policy_version_id=None,
    )
    assert decision.decision == "DENY"
