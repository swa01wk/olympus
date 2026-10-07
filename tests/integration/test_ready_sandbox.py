from __future__ import annotations

import pytest
from core.config.settings import OlympusSettings
from core.execution.sandbox.runner import sandbox_available

pytestmark = pytest.mark.integration


def test_sandbox_available_in_test_env() -> None:
    settings = OlympusSettings(olympus_env="test")
    assert sandbox_available(settings) is True


def test_journey_env_requires_bwrap_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLYMPUS_ENV", "integration")
    settings = OlympusSettings(olympus_env="integration")
    import core.execution.sandbox.bwrap as bwrap_mod

    monkeypatch.setattr(bwrap_mod, "bubblewrap_available", lambda: False)
    assert sandbox_available(settings) is False
