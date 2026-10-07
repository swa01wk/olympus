"""Phase 08 §15 — handoff documentation exists for Phase 09/10."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
HANDOFF = ROOT / "docs" / "phase08-handoff-09-10.md"


def test_phase08_handoff_doc_present() -> None:
    assert HANDOFF.is_file(), "docs/phase08-handoff-09-10.md required for §15 exit"


def test_phase08_handoff_doc_covers_policy_and_lineage() -> None:
    text = HANDOFF.read_text(encoding="utf-8")
    assert "FindingPolicy" in text
    assert "register_hop" in text
    assert "register_obligation_source" in text
    assert "release_hook" in text or "recompute_release_eligibility" in text
