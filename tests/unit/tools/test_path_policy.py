import pytest
from core.tools.paths import PathPolicyViolation, resolve_in_workspace


@pytest.mark.unit
def test_path_traversal_denied(tmp_path) -> None:
    ws = tmp_path / "wt"
    ws.mkdir()
    with pytest.raises(PathPolicyViolation):
        resolve_in_workspace(ws, "../outside")


@pytest.mark.unit
def test_git_path_denied(tmp_path) -> None:
    ws = tmp_path / "wt"
    ws.mkdir()
    (ws / ".git").mkdir()
    with pytest.raises(PathPolicyViolation):
        resolve_in_workspace(ws, ".git/config")
