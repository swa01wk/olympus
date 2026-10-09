from pathlib import Path

import pytest
from core.assurance.deterministic_plan import resolve_existing_test_node
from core.execution.snapshots.product_context import missing_protected_tests

pytestmark = pytest.mark.unit


def test_missing_protected_tests_detects_renamed_function(tmp_path: Path) -> None:
    service = tmp_path / "tests" / "test_ticket_service.py"
    service.parent.mkdir()
    service.write_text("def test_create_ticket_defaults_priority_to_medium():\n    assert True\n")
    missing = missing_protected_tests(
        tmp_path,
        [
            "tests/test_ticket_service.py::test_create_defaults_open",
            "tests/test_tickets_api.py::test_create_ticket",
        ],
    )
    assert missing == [
        "tests/test_ticket_service.py::test_create_defaults_open",
        "tests/test_tickets_api.py::test_create_ticket",
    ]


def test_missing_protected_tests_passes_when_function_exists(tmp_path: Path) -> None:
    service = tmp_path / "tests" / "test_ticket_service.py"
    service.parent.mkdir()
    service.write_text("def test_create_defaults_open():\n    assert True\n")
    assert (
        missing_protected_tests(
            tmp_path, ["tests/test_ticket_service.py::test_create_defaults_open"]
        )
        == []
    )


def test_resolve_existing_test_node_falls_back_to_same_file() -> None:
    nodes = {
        "tests/test_ticket_service.py::test_create_ticket_defaults_priority_to_medium",
        "tests/test_tickets_api.py::test_create_ticket",
    }
    assert (
        resolve_existing_test_node("tests/test_ticket_service.py::test_create_defaults_open", nodes)
        == "tests/test_ticket_service.py::test_create_ticket_defaults_priority_to_medium"
    )
    assert (
        resolve_existing_test_node("tests/test_tickets_api.py::test_create_ticket", nodes)
        == "tests/test_tickets_api.py::test_create_ticket"
    )
    assert resolve_existing_test_node("tests/gone.py::test_x", nodes) is None
