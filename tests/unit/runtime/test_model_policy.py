from __future__ import annotations

import os

import pytest
from core.config.settings import clear_settings_cache
from core.runtime.errors import ConfigError
from core.runtime.model_policy import ModelPolicy, clear_models_config_cache

pytestmark = pytest.mark.unit


def test_resolve_verification_alias() -> None:
    os.environ["MODEL_DEFAULT"] = "claude-test"
    os.environ["MODEL_VERIFICATION"] = "claude-verification"
    clear_settings_cache()
    clear_models_config_cache()
    resolved = ModelPolicy().resolve("verification_planning")
    assert resolved.model == "claude-verification"
    assert resolved.alias == "verification_planning"


def test_unknown_alias_raises() -> None:
    with pytest.raises(ConfigError, match="Unknown model alias"):
        ModelPolicy().resolve("not_a_real_alias")
