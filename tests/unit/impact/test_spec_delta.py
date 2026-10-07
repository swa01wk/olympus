from __future__ import annotations

from core.product_model.specifications.delta import _align_by_lineage, _align_text_lists


def test_align_ac_modified() -> None:
    before = [{"lineage_key": "AC-1", "statement": "old"}]
    after = [{"lineage_key": "AC-1", "statement": "new"}]
    out = _align_by_lineage(before, after, fields=("statement",))
    assert out["modified"][0]["lineage_key"] == "AC-1"
    assert out["added"] == []
    assert out["removed"] == []


def test_align_requirement_removed() -> None:
    before = [{"lineage_key": "REQ-1", "statement": "x"}]
    after: list[dict] = []
    out = _align_by_lineage(before, after, fields=("statement",))
    assert len(out["removed"]) == 1


def test_align_rules_text() -> None:
    out = _align_text_lists(["a"], ["a", "b"])
    assert out["added"] == ["b"]
    assert out["removed"] == []
