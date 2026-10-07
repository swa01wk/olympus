from __future__ import annotations

import uuid

import pytest
from core.integration.ordering import order_candidates, topological_order_task_ids


def test_topological_diamond() -> None:
    a, b, c, d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    keys = {a: "T-A", b: "T-B", c: "T-C", d: "T-D"}
    order = topological_order_task_ids(
        {a, b, c, d},
        [(b, a), (c, a), (d, b), (d, c)],
        keys,
    )
    assert order.index(a) < order.index(b)
    assert order.index(a) < order.index(c)
    assert order.index(b) < order.index(d)
    assert order.index(c) < order.index(d)


def test_topological_chain() -> None:
    t1, t2, t3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    keys = {t1: "T-001", t2: "T-002", t3: "T-003"}
    order = topological_order_task_ids({t1, t2, t3}, [(t2, t1), (t3, t2)], keys)
    assert order == [t1, t2, t3]


def test_skip_already_ancestor(monkeypatch: pytest.MonkeyPatch) -> None:
    """Second commit already on merged head lineage is skipped without git fixture."""

    def fake_is_ancestor(_path: object, ancestor: str, descendant: str) -> bool:
        return ancestor == descendant or (ancestor == "base" and descendant == "child")

    monkeypatch.setattr(
        "core.integration.ordering.GitInspector.is_ancestor",
        lambda self, path, ancestor, descendant: fake_is_ancestor(path, ancestor, descendant),
    )
    t1, t2 = uuid.uuid4(), uuid.uuid4()
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    ordered = order_candidates(
        git_dir_path="/tmp/unused",
        base_sha="base",
        entries=[
            (t1, "T-1", c1, "child"),
            (t2, "T-2", c2, "base"),
        ],
        dependency_edges=[],
    )
    assert ordered[0].included is True
    assert ordered[1].included is False
    assert ordered[1].skip_reason == "ALREADY_ANCESTOR"
