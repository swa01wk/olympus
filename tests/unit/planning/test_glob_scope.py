import pytest
from core.planning.glob_scope import (
    intersect_scopes,
    normalize_pattern,
    path_matches_pattern,
    pattern_allowed,
    scope_contains,
)

pytestmark = pytest.mark.unit


def test_recursive_py_glob_is_an_alias_for_dir_py() -> None:
    assert normalize_pattern("app/api/**/*.py") == "app/api/*.py"
    assert pattern_allowed("app/api/**/*.py")
    assert path_matches_pattern("app/api/routes/tickets.py", "app/api/**/*.py")
    assert path_matches_pattern("app/api/tickets.py", "app/api/**/*.py")
    assert not path_matches_pattern("app/api/README.md", "app/api/**/*.py")


def test_recursive_py_glob_is_contained_by_dir_scope() -> None:
    assert scope_contains(["app/api/**"], ["app/api/**/*.py"])
    assert intersect_scopes(["app/api/**/*.py"], ["app/api/**"]) == ["app/api/*.py"]


def test_other_mid_path_double_star_globs_stay_rejected() -> None:
    assert not pattern_allowed("app/**/api/*.py")
    assert not pattern_allowed("app/api/**/*.ts")
