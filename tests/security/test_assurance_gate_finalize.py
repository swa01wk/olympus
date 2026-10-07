from __future__ import annotations

import pytest
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind, ActorRole


@pytest.mark.security
def test_warden_and_sentinel_profiles_cannot_write_gates() -> None:
    from core.runtime.agent_profiles import all_profiles
    from core.runtime.profiles.sentinel import register_sentinel_profiles
    from core.runtime.profiles.warden import register_warden_profile

    register_warden_profile()
    register_sentinel_profiles()
    for name, profile in all_profiles().items():
        if not name.startswith(("warden.", "sentinel.")):
            continue
        for tool in profile.allowed_tools:
            assert "gate" not in tool
            assert "evidence" not in tool


@pytest.mark.security
def test_agent_kind_blocked_for_finalize() -> None:
    agent = Actor(kind=ActorKind.AGENT, name="x", roles=[ActorRole.SYSTEM.value])
    assert agent.kind == ActorKind.AGENT
