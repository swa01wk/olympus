from core.review.auto_request import ensure_pending_approval
from core.review.completion import complete_revision_if_needed, revision_approval_id_from_execution
from core.review.context import RevisionContext
from core.review.contract_snapshot import attach_snapshot, merge_revision_snapshot

__all__ = [
    "RevisionContext",
    "attach_snapshot",
    "ensure_pending_approval",
    "complete_revision_if_needed",
    "merge_revision_snapshot",
    "revision_approval_id_from_execution",
]
