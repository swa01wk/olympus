from __future__ import annotations

from typing import Any

from core.review.context import RevisionContext


def merge_revision_snapshot(
    existing: dict[str, Any] | None,
    revision: RevisionContext | None,
) -> dict[str, Any] | None:
    if revision is None:
        return existing
    merged = dict(existing or {})
    merged["revision_feedback"] = revision.feedback
    merged["previous_output_json"] = revision.previous_output_json
    merged["revision_of_approval_id"] = str(revision.approval_id)
    return merged


def attach_snapshot(
    body_json: dict[str, Any],
    *,
    snapshot: dict[str, Any] | None = None,
    revision: RevisionContext | None = None,
) -> dict[str, Any]:
    snap = merge_revision_snapshot(snapshot, revision)
    if snap is None:
        return body_json
    return {**body_json, "_snapshot": snap}
