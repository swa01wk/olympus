"""`olympus start` decides the journey from the folder and calls Olympus correctly."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from apps.cli import main as cli

pytestmark = [pytest.mark.unit]

PRD = "# Notes\n\nA small app for keeping notes, with tags and search.\n"


def _git(folder: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=folder,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, Any]]:
    recorded: list[tuple[str, str, Any]] = []

    def fake_api(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        recorded.append((method, path, body))
        if path == "/actors/me":
            return {"actor_id": "a1", "name": "you"}
        if path.startswith("/local-projects"):
            return None
        return {
            "project_id": "p1",
            "delivery_cycle_id": "c1",
            "autopilot": {"message": "Reading your PRD"},
        }

    monkeypatch.setattr(cli, "api", fake_api)
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: True)
    # Commits made by the CLI need an identity on machines without a global git config.
    monkeypatch.setenv("GIT_AUTHOR_NAME", "t")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "t@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "t")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "t@example.com")
    return recorded


def _start(folder: Path, monkeypatch: pytest.MonkeyPatch, *extra: str) -> int:
    monkeypatch.chdir(folder)
    return cli.main(["start", "--no-open", *extra])


def test_new_folder_with_prd_starts_a_new_app_and_sets_up_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, calls, capsys
) -> None:
    (tmp_path / "PRD.md").write_text(PRD)
    assert _start(tmp_path, monkeypatch) == 0
    method, path, body = calls[-1]
    assert (method, path) == ("POST", "/start")
    assert body["journey"] == "GREENFIELD_BUILD"
    assert body["prd_text"] == PRD
    assert body["prd_title"] == "PRD.md"
    assert body["local_path"] == str(tmp_path.resolve())
    assert body["name"] == tmp_path.name
    assert (tmp_path / ".git").exists()
    out = capsys.readouterr().out
    assert "olympus/..." in out
    assert "http://127.0.0.1:3010/runs/c1" in out


def test_new_folder_without_prd_explains_what_to_do(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, calls, capsys
) -> None:
    assert _start(tmp_path, monkeypatch) == 1
    assert not [c for c in calls if c[1] == "/start"]
    assert "PRD.md" in capsys.readouterr().out


def test_existing_repo_starts_onboarding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, calls
) -> None:
    (tmp_path / "main.go").write_text("package main\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "init")
    assert _start(tmp_path, monkeypatch, "--name", "Go App") == 0
    _, _, body = calls[-1]
    assert body == {
        "journey": "BROWNFIELD_ONBOARDING",
        "name": "Go App",
        "local_path": str(tmp_path.resolve()),
    }


def test_uncommitted_changes_warn_and_continue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, calls, capsys
) -> None:
    (tmp_path / "app.py").write_text("x = 1\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "init")
    (tmp_path / "app.py").write_text("x = 2\n")
    assert _start(tmp_path, monkeypatch) == 0
    assert "uncommitted changes" in capsys.readouterr().out
    assert calls[-1][2]["journey"] == "BROWNFIELD_ONBOARDING"
    assert (tmp_path / "app.py").read_text() == "x = 2\n"


def test_code_without_git_needs_a_yes_before_committing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, calls
) -> None:
    (tmp_path / "app.py").write_text("x = 1\n")
    # No terminal to ask on, no --yes: refuse and change nothing.
    assert _start(tmp_path, monkeypatch) == 1
    assert not (tmp_path / ".git").exists()

    assert _start(tmp_path, monkeypatch, "--yes") == 0
    assert _git(tmp_path, "log", "--format=%s") == "Initial commit (before Olympus)"
    assert calls[-1][2]["journey"] == "BROWNFIELD_ONBOARDING"


def test_never_auto_commits_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, calls, capsys
) -> None:
    (tmp_path / "app.py").write_text("x = 1\n")
    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-123\n")
    assert _start(tmp_path, monkeypatch, "--yes") == 1
    assert not (tmp_path / ".git").exists()
    assert ".env" in capsys.readouterr().out


def test_folder_that_is_already_a_project_shows_its_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    def fake_api(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        assert method == "GET", "must not start a second project"
        if path == "/actors/me":
            return {"actor_id": "a1"}
        return {
            "name": "Notes",
            "latest_run": {
                "delivery_cycle_id": "c9",
                "autopilot": {"status": "NEEDS_YOU", "message": "Review the design"},
            },
        }

    monkeypatch.setattr(cli, "api", fake_api)
    assert _start(tmp_path, monkeypatch) == 0
    out = capsys.readouterr().out
    assert "already the Olympus project “Notes”" in out
    assert "needs you — Review the design" in out


def test_olympus_not_running_is_a_friendly_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    token = tmp_path / "token"
    token.write_text("t")
    monkeypatch.setattr(cli, "TOKEN_FILE", token)
    monkeypatch.setattr(cli, "API_URL", "http://127.0.0.1:9")
    monkeypatch.chdir(tmp_path)
    assert cli.main(["status"]) == 1
    assert "make dev" in capsys.readouterr().err


def test_rejected_sign_in_changes_nothing_in_the_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    (tmp_path / "PRD.md").write_text(PRD)

    def fake_api(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        assert path == "/actors/me", "nothing else may be called"
        raise cli.CliError("Olympus said: Invalid or revoked token")

    monkeypatch.setattr(cli, "api", fake_api)
    assert _start(tmp_path, monkeypatch) == 1
    assert not (tmp_path / ".git").exists()
    assert "make dev" in capsys.readouterr().err


def test_failed_start_leaves_a_new_folder_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "PRD.md").write_text(PRD)

    def fake_api(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        if path == "/actors/me":
            return {"actor_id": "a1"}
        if path.startswith("/local-projects"):
            return None
        raise cli.CliError("Olympus said: database is down")

    monkeypatch.setattr(cli, "api", fake_api)
    assert _start(tmp_path, monkeypatch) == 1
    assert not (tmp_path / ".git").exists()
