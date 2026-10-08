from __future__ import annotations

import uuid

import pytest
from core.review.context import RevisionContext
from core.review.contract_snapshot import attach_snapshot, merge_revision_snapshot

pytestmark = pytest.mark.unit


def test_merge_revision_snapshot_without_revision_returns_existing() -> None:
    base = {"implementation_spec_mode": "REPAIR", "project_name": "p"}
    assert merge_revision_snapshot(base, None) is base


def test_merge_revision_snapshot_merges_keys() -> None:
    approval_id = uuid.uuid4()
    revision = RevisionContext(
        approval_id=approval_id,
        feedback="fix guard",
        previous_output_json='{"x": 1}',
        subject_type="architecture",
        subject_id=uuid.uuid4(),
    )
    merged = merge_revision_snapshot({"implementation_spec_mode": "REPAIR"}, revision)
    assert merged == {
        "implementation_spec_mode": "REPAIR",
        "revision_feedback": "fix guard",
        "previous_output_json": '{"x": 1}',
        "revision_of_approval_id": str(approval_id),
    }


def test_attach_snapshot_skips_snapshot_key_when_empty() -> None:
    body = {"objective": "x", "work_type": "ANALYSIS"}
    assert attach_snapshot(body, revision=None) == body
    assert "_snapshot" not in attach_snapshot(body, revision=None)


def test_attach_snapshot_adds_revision_only_snapshot() -> None:
    approval_id = uuid.uuid4()
    revision = RevisionContext(
        approval_id=approval_id,
        feedback="n",
        previous_output_json="{}",
        subject_type="architecture",
        subject_id=uuid.uuid4(),
    )
    body = {"objective": "x"}
    out = attach_snapshot(body, revision=revision)
    assert out["_snapshot"]["revision_feedback"] == "n"
    assert out["objective"] == "x"
