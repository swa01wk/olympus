from __future__ import annotations

import pytest
from core.assurance.carry_forward import entity_sets_unchanged

pytestmark = pytest.mark.unit


def test_entity_sets_unchanged_true() -> None:
    prior = {"k1": "h1", "k2": "h2"}
    current = {"k2": "h2", "k1": "h1"}
    assert entity_sets_unchanged(prior, current)


def test_entity_sets_unchanged_false_on_hash() -> None:
    assert not entity_sets_unchanged({"k1": "h1"}, {"k1": "h2"})


def test_entity_sets_unchanged_false_on_keys() -> None:
    assert not entity_sets_unchanged({"k1": "h1"}, {"k1": "h1", "k2": "h2"})
