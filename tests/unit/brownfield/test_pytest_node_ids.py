from __future__ import annotations

from pathlib import Path

from core.assurance.pytest_node import junit_case_node_id, legacy_node_to_path
from core.intelligence.baselines.authored import AUTHORED_TEST_DIR, authored_test_path


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "tests" / "api").mkdir(parents=True)
    (tmp_path / "tests" / "test_tickets_api.py").write_text("")
    (tmp_path / "tests" / "api" / "test_flow.py").write_text("")
    return tmp_path


def test_junit_function_case_maps_to_file_node(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert (
        junit_case_node_id(repo, "tests.test_tickets_api", "test_create_ticket")
        == "tests/test_tickets_api.py::test_create_ticket"
    )


def test_junit_class_case_keeps_class_segment(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert (
        junit_case_node_id(repo, "tests.api.test_flow.TestFlow", "test_ok")
        == "tests/api/test_flow.py::TestFlow::test_ok"
    )


def test_junit_unknown_module_falls_back_to_classname(tmp_path: Path) -> None:
    assert junit_case_node_id(tmp_path, "pkg.missing", "test_x") == "pkg.missing::test_x"


def test_legacy_dotted_node_is_rewritten_and_path_nodes_kept(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert (
        legacy_node_to_path(repo, "tests.test_tickets_api::test_create_ticket")
        == "tests/test_tickets_api.py::test_create_ticket"
    )
    assert (
        legacy_node_to_path(repo, "tests/test_tickets_api.py::t") == "tests/test_tickets_api.py::t"
    )
    assert legacy_node_to_path(repo, "tests/test_tickets_api.py") == "tests/test_tickets_api.py"


def test_authored_test_path_is_confined_to_characterization_dir() -> None:
    path = authored_test_path("BL-0003", "../../app/evil.py")
    assert path == f"{AUTHORED_TEST_DIR}/test_evil_bl_0003.py"
    assert (
        authored_test_path("BL-0004", None)
        == f"{AUTHORED_TEST_DIR}/test_characterization_bl_0004.py"
    )
    assert authored_test_path("BL-0005", "test_create.py").endswith("/test_create_bl_0005.py")
