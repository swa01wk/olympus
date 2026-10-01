from __future__ import annotations

from pathlib import Path

import pytest
from core.config.settings import OlympusSettings, clear_settings_cache, get_settings
from pydantic import SecretStr, ValidationError


@pytest.mark.unit
def test_settings_defaults_resolve_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = tmp_path / "workspaces"
    monkeypatch.setenv("OLYMPUS_WORKSPACE_ROOT", str(ws))
    monkeypatch.setenv("OLYMPUS_STORAGE_ROOT", str(tmp_path / "storage"))
    clear_settings_cache()
    settings = get_settings()
    assert settings.olympus_workspace_root.is_absolute()
    assert settings.olympus_workspace_root.exists()
    assert settings.olympus_worktree_root is not None
    assert settings.olympus_worktree_root.is_absolute()


@pytest.mark.unit
def test_settings_env_override(tmp_path: Path) -> None:
    settings = OlympusSettings(
        olympus_env="integration",
        olympus_workspace_root=tmp_path / "ws",
        olympus_storage_root=tmp_path / "storage",
        database_url="postgresql+psycopg://example",
    )
    assert settings.olympus_env == "integration"
    assert str(settings.database_url).startswith("postgresql")


@pytest.mark.unit
def test_secret_str_redacted_in_repr(tmp_path: Path) -> None:
    settings = OlympusSettings(
        olympus_workspace_root=tmp_path / "ws",
        olympus_storage_root=tmp_path / "storage",
        olympus_secret_key=SecretStr("super-secret"),
    )
    text = repr(settings)
    assert "super-secret" not in text
    assert "**********" in text or "SecretStr" in text


@pytest.mark.unit
def test_journey_requires_live_llm(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="LLM_LIVE_TESTS=1"):
        OlympusSettings(
            olympus_env="journey",
            llm_live_tests=0,
            olympus_workspace_root=tmp_path / "ws",
            olympus_storage_root=tmp_path / "storage",
        )


@pytest.mark.unit
def test_relative_workspace_root_becomes_absolute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    settings = OlympusSettings(
        olympus_workspace_root=Path("./relative/ws"),
        olympus_storage_root=tmp_path / "storage",
    )
    assert settings.olympus_workspace_root.is_absolute()
    assert settings.olympus_workspace_root.name == "ws"


@pytest.mark.unit
def test_unwritable_workspace_root_fails(tmp_path: Path) -> None:
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    blocked.chmod(0o444)
    try:
        with pytest.raises(ValidationError, match="not writable"):
            OlympusSettings(
                olympus_workspace_root=blocked,
                olympus_storage_root=tmp_path / "storage",
            )
    finally:
        blocked.chmod(0o755)
