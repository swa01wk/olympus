from __future__ import annotations

from core.integration.remediation import summarize_check_output

_LOG = """compileall rc=0

collect rc=0
27 tests collected
pytest rc=1
../../.venv/lib/python3.12/site-packages/starlette/testclient.py:463: in request
/usr/lib/python3.12/concurrent/futures/_base.py:456: in result
app/api/links.py:36: in list_links
E       pydantic_core._pydantic_core.ValidationError: 1 validation error for LinkRead
app/api/links.py:21: ValidationError
  /home/me/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1464: PytestConfigWarning
E       assert 200 == 404
tests/test_link_api.py:224: AssertionError
FAILED tests/test_link_api.py::test_list_update_disable_enable_delete_endpoints
FAILED tests/test_link_api.py::test_analytics_prefix_not_exposed_by_contract
2 failed, 25 passed, 1 warning in 1.29s
"""


def test_summary_keeps_failures_and_causes_and_drops_library_frames() -> None:
    summary = summarize_check_output(_LOG)
    assert "FAILED tests/test_link_api.py::test_analytics_prefix_not_exposed_by_contract" in summary
    assert "ValidationError: 1 validation error for LinkRead" in summary
    assert "app/api/links.py:36: in list_links" in summary
    assert "tests/test_link_api.py:224: AssertionError" in summary
    assert "2 failed, 25 passed" in summary
    assert "site-packages" not in summary
    assert "concurrent/futures" not in summary


def test_summary_falls_back_to_log_tail_and_respects_limit() -> None:
    log = "x" * 50 + "\nsomething odd happened\n"
    assert summarize_check_output(log).endswith("something odd happened\n")
    many = "".join(f"FAILED tests/test_{i}.py::t\n" for i in range(500))
    assert len(summarize_check_output(many, limit=100)) <= 100
