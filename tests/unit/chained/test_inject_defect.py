"""Unit tests for defect injector target selection (Phase 19 §12)."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.demo.chained.inject_defect import (
    InjectionError,
    find_409_raise_sites,
    inject_defect_in_tree,
)

FIXTURE = (
    Path(__file__).resolve().parents[2] / "fixtures" / "repos" / "supportdesk_defect_closed_update"
)


@pytest.mark.unit
def test_find_single_409_raise_site() -> None:
    source = (FIXTURE / "app/services/ticket_service.py").read_text(encoding="utf-8")
    sites = find_409_raise_sites(FIXTURE / "app/services/ticket_service.py", source)
    assert len(sites) == 1


@pytest.mark.unit
def test_inject_transforms_to_runtime_error() -> None:
    new_source = inject_defect_in_tree(FIXTURE)
    assert "RuntimeError" in new_source
    assert "409" not in new_source.split("RuntimeError", 1)[0]


@pytest.mark.unit
def test_ambiguous_when_two_raises(tmp_path: Path) -> None:
    body = """
def a():
    raise HTTPException(status_code=409)
def b():
    raise HTTPException(status_code=409)
"""
    path = tmp_path / "svc.py"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(ValueError, match=InjectionError.INJECTION_TARGET_AMBIGUOUS):
        inject_defect_in_tree(tmp_path, rel_path="svc.py")
