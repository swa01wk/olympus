from __future__ import annotations

import uuid

import pytest
from core.config.settings import OlympusSettings
from core.repositories.workspace_locator import WorkspaceLocator

pytestmark = pytest.mark.unit


@pytest.fixture
def locator(tmp_path) -> WorkspaceLocator:
    settings = OlympusSettings(
        database_url="postgresql+psycopg://x:x@localhost/x",
        olympus_workspace_root=tmp_path / "ws",
        olympus_storage_root=tmp_path / "storage",
        olympus_env="test",
        olympus_worktree_root=tmp_path / "wt",
    )
    return WorkspaceLocator(settings)


def test_canonical_and_execution_locations(locator: WorkspaceLocator) -> None:
    pid = uuid.uuid4()
    assert locator.canonical_location(pid) == f"projects/{pid}/repo"
    assert locator.execution_location(pid, "EX-1") == f"projects/{pid}/worktrees/EX-1"


def test_rejects_traversal_and_absolute(locator: WorkspaceLocator) -> None:
    with pytest.raises(ValueError):
        locator.resolve("LOCAL_FILESYSTEM", "../escape")
    with pytest.raises(ValueError):
        locator.resolve("LOCAL_FILESYSTEM", "/etc/passwd")


def test_worktree_root_override(locator: WorkspaceLocator, tmp_path) -> None:
    pid = uuid.uuid4()
    logical = locator.execution_location(pid, "k")
    path = locator.resolve("LOCAL_FILESYSTEM", logical)
    assert str(tmp_path / "wt") in str(path)


def test_same_logical_different_roots(locator: WorkspaceLocator, tmp_path) -> None:
    pid = uuid.uuid4()
    canonical = locator.resolve("LOCAL_FILESYSTEM", locator.canonical_location(pid))
    worktree = locator.resolve("LOCAL_FILESYSTEM", locator.execution_location(pid, "k"))
    assert canonical != worktree
    assert str(tmp_path / "ws") in str(canonical)
    assert str(tmp_path / "wt") in str(worktree)
