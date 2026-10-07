from __future__ import annotations

import os

import pytest
from core.runtime.budget import get_budget_ledger

from tests.live_credentials import any_live_provider_configured


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--live-required",
        action="store_true",
        default=False,
        help="Fail the session if live_llm tests are skipped",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "live_llm: tests requiring live LLM providers")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[object]) -> None:
    outcome = yield
    report = outcome.get_result()
    if not item.config.getoption("--live-required"):
        return
    if "live_llm" not in item.keywords:
        return
    if report.when == "setup" and report.skipped:
        pytest.fail(f"live_llm test skipped but --live-required was set: {report.longrepr}")


@pytest.hookimpl(trylast=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    live_required = item.config.getoption("--live-required")
    if not live_required:
        return
    if "live_llm" not in item.keywords:
        return
    if os.environ.get("LLM_LIVE_TESTS", "0") != "1":
        pytest.fail("live_llm tests require LLM_LIVE_TESTS=1 when --live-required is set")
    if not any_live_provider_configured():
        pytest.fail(
            "live_llm tests require ANTHROPIC_API_KEY or OPENAI_API_KEY (env or .env via settings)"
        )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    ledger = get_budget_ledger()
    spent = ledger.session_spent
    if spent > 0:
        reporter = session.config.pluginmanager.getplugin("terminalreporter")
        if reporter is not None:
            reporter.write_line(f"\nLive LLM session spend (estimate): ${spent}")
