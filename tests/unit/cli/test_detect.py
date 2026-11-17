"""`olympus start` folder detection: new project vs existing code."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from apps.cli.detect import detect, find_prd, is_doc, looks_secret

pytestmark = [pytest.mark.unit]


def _git(folder: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=folder,
        check=True,
        capture_output=True,
    )


def test_empty_folder_is_new(tmp_path: Path) -> None:
    found = detect(tmp_path)
    assert found.kind == "new"
    assert not found.is_git
    assert found.prd is None


def test_folder_with_only_docs_is_new_and_finds_the_prd(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# My app")
    (tmp_path / "PRD.md").write_text("# My app\n\nA ticket tracker.")
    (tmp_path / "LICENSE").write_text("MIT")
    (tmp_path / ".gitignore").write_text(".env\n")
    found = detect(tmp_path)
    assert found.kind == "new"
    assert found.prd == tmp_path / "PRD.md"


def test_prd_in_docs_and_explicit_prd(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "PRD.md").write_text("x")
    assert find_prd(tmp_path) == tmp_path / "docs" / "PRD.md"
    assert find_prd(tmp_path, "spec/app.md") == (tmp_path / "spec" / "app.md").resolve()


def test_code_makes_it_existing_even_without_git(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("print('hi')\n")
    found = detect(tmp_path)
    assert found.kind == "existing"
    assert not found.is_git
    assert found.code_files == ["app/main.py"]


def test_dependency_folders_are_not_counted_as_code(tmp_path: Path) -> None:
    (tmp_path / "node_modules" / "left-pad").mkdir(parents=True)
    (tmp_path / "node_modules" / "left-pad" / "index.js").write_text("module.exports=1")
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / ".venv" / "lib" / "site.py").write_text("")
    assert detect(tmp_path).kind == "new"


def test_git_repo_reports_commits_and_uncommitted_changes(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / "server.js").write_text("console.log(1)\n")
    found = detect(tmp_path)
    assert (found.kind, found.is_git, found.has_commits, found.dirty) == (
        "existing",
        True,
        False,
        True,
    )
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "init")
    found = detect(tmp_path)
    assert (found.has_commits, found.dirty) == (True, False)
    (tmp_path / "server.js").write_text("console.log(2)\n")
    assert detect(tmp_path).dirty


def test_gitignored_files_do_not_count(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / ".gitignore").write_text("out/\n")
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "bundle.js").write_text("x")
    assert detect(tmp_path).kind == "new"


def test_is_doc() -> None:
    assert is_doc("README")
    assert is_doc("docs/guide.md")
    assert is_doc("CHANGELOG.rst")
    assert not is_doc("src/readme_parser.py")
    assert not is_doc("Makefile")


def test_secret_looking_files_block_auto_commit(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("")
    (tmp_path / ".env").write_text("KEY=1")
    (tmp_path / ".env.example").write_text("KEY=")
    (tmp_path / "certs").mkdir()
    (tmp_path / "certs" / "server.pem").write_text("")
    assert looks_secret(tmp_path) == [".env", "certs/server.pem"]
    _git(tmp_path, "init", "-q")
    (tmp_path / ".gitignore").write_text(".env\ncerts/\n")
    assert looks_secret(tmp_path) == []
