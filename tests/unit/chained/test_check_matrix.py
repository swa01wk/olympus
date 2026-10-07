"""Unit tests for acceptance matrix checker (Phase 19 §12)."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path


def _write_junit(path: Path, *, classname: str, name: str, outcome: str) -> None:
    if outcome == "skipped":
        case = f'<testcase classname="{classname}" name="{name}"><skipped/></testcase>'
    elif outcome == "failed":
        case = f'<testcase classname="{classname}" name="{name}"><failure/></testcase>'
    else:
        case = f'<testcase classname="{classname}" name="{name}"/>'
    path.write_text(
        textwrap.dedent(
            f"""\
            <?xml version="1.0" encoding="utf-8"?>
            <testsuite>{case}</testsuite>
            """
        ),
        encoding="utf-8",
    )


def test_matrix_missing_test_fails(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.yaml"
    matrix.write_text(
        "- id: ROW1\n  tests:\n    - tests.foo::test_bar\n",
        encoding="utf-8",
    )
    junit = tmp_path / "empty.xml"
    _write_junit(junit, classname="tests.other", name="test_ok", outcome="passed")
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/acceptance/check_matrix.py",
            "--matrix",
            str(matrix),
            "--junit",
            str(junit),
        ],
        cwd=Path(__file__).resolve().parents[3],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0


def test_matrix_skipped_counts_as_failed(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.yaml"
    matrix.write_text(
        "- id: ROW1\n  tests:\n    - tests.foo::test_bar\n",
        encoding="utf-8",
    )
    junit = tmp_path / "skip.xml"
    _write_junit(junit, classname="tests.foo", name="test_bar", outcome="skipped")
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/acceptance/check_matrix.py",
            "--matrix",
            str(matrix),
            "--junit",
            str(junit),
        ],
        cwd=Path(__file__).resolve().parents[3],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
