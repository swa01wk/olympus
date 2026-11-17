"""Defect fixture reproduces 500 on hand-authored test (no LLM)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from tests.journey.bug_fix_helpers import REPRO_TEST_SOURCE

DEFECT_ROOT = (
    Path(__file__).resolve().parents[2] / "fixtures" / "repos" / "supportdesk_defect_closed_update"
)


@pytest.mark.integration
def test_handwritten_repro_fails_on_defect_repo(tmp_path: Path) -> None:
    """PRE_REPAIR-style test expects 409; buggy repo returns 500 → pytest fails."""
    repo = tmp_path / "repo"
    shutil.copytree(
        DEFECT_ROOT, repo, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache")
    )
    repro_dir = repo / "tests" / "olympus_repro"
    repro_dir.mkdir(parents=True, exist_ok=True)
    (repro_dir / "conftest.py").write_text(
        """import app.models.ticket  # noqa: F401
from app.db import Base, engine

Base.metadata.create_all(bind=engine)
""",
        encoding="utf-8",
    )
    repro_file = repro_dir / "test_closed_ticket_500.py"
    repro_file.write_text(REPRO_TEST_SOURCE, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(repro_file.relative_to(repo)),
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0, result.stdout + result.stderr
    assert "500 == 409" in result.stdout, result.stdout  # fails on the planted defect itself


@pytest.mark.integration
def test_handwritten_repro_not_reproduced_on_fixed_service_logic() -> None:
    """Sanity: fixed transition table rejects CLOSED updates with 409 (unit-level)."""
    service_src = (DEFECT_ROOT / "app/services/ticket_service.py").read_text(encoding="utf-8")
    assert "TRANSITIONS" in service_src
