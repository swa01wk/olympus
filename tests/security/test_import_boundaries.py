from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.mark.security
def test_agents_no_persistence_contract(project_root: Path | None = None) -> None:
    root = project_root or Path(__file__).resolve().parents[2]
    violation = root / "agents" / "_import_violation_probe.py"
    violation.write_text("from core.db import Base\n", encoding="utf-8")
    lint_imports = root / ".venv" / "bin" / "lint-imports"
    cmd = [str(lint_imports)] if lint_imports.is_file() else ["uv", "run", "lint-imports"]
    try:
        result = subprocess.run(
            cmd,
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0
        assert "agents-no-persistence" in (result.stdout + result.stderr)
    finally:
        violation.unlink(missing_ok=True)
