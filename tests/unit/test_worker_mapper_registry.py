"""Worker entrypoints register every ORM mapper (fresh interpreter, no test imports)."""

from __future__ import annotations

import subprocess
import sys

import pytest

pytestmark = pytest.mark.unit

_PROBE = (
    "import {module}\n"
    "import core.product_model.changes.models\n"
    "from core.db.base import Base\n"
    "from sqlalchemy.orm import configure_mappers\n"
    "configure_mappers()\n"
    "for table in Base.metadata.tables.values():\n"
    "    for fk in table.foreign_keys:\n"
    "        fk.column\n"
)


@pytest.mark.parametrize("module", ["apps.execution_worker.main", "apps.scheduler_worker.main"])
def test_worker_entrypoint_configures_all_mappers(module: str) -> None:
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE.format(module=module)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
