"use client";

import { Button } from "@/components/primitives";
import { useStudioDecisionNote } from "@/lib/studio-decision-note";
import type { OrchestratorRevisionNoteDraft } from "@/src/api/types/orchestrator";

export function RevisionNoteDraftCard({ draft }: { draft: OrchestratorRevisionNoteDraft }) {
  const { applyDraftNote } = useStudioDecisionNote();

  return (
    <div className="ol-chat-revision-draft">
      <p className="ol-label">Revision note draft</p>
      <blockquote className="ol-body-sm">{draft.note}</blockquote>
      <p className="ol-body-sm ol-muted">
        Approval <span className="ol-id">{draft.approval_id}</span>
      </p>
      <Button
        variant="primary"
        type="button"
        onClick={() => applyDraftNote(draft.approval_id, draft.note)}
      >
        Use in decision panel
      </Button>
    </div>
  );
}
