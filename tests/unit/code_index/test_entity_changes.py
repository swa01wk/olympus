from __future__ import annotations

from core.integration.enums import EntityChangeKind
from core.intelligence.code_index.changes import diff_stable_keys


def test_entity_diff_kinds() -> None:
    base_map = {"k1": "h1", "k2": "h2"}
    cand_map = {"k1": "h1new", "k3": "h3"}
    kinds = diff_stable_keys(base_map, cand_map)
    assert kinds["k1"] == EntityChangeKind.MODIFIED
    assert kinds["k2"] == EntityChangeKind.DELETED
    assert kinds["k3"] == EntityChangeKind.ADDED
