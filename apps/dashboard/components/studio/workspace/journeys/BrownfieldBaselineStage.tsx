"use client";

import { EmptyState, Panel, StatusBadge } from "@/components/primitives";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import { useReviewQueue } from "@/src/api/hooks/use-journey-queries";

export function BrownfieldBaselineStage({ cycleId }: { cycleId: string }) {
  const queue = useReviewQueue(cycleId);

  return (
    <StageWorkspaceFrame>
      <Panel title="Review queue" sub={`GET /delivery-cycles/${cycleId}/review-queue`}>
        {queue.isLoading && <p className="ol-body-sm ol-muted">Loading…</p>}
        {(queue.data ?? []).length === 0 && !queue.isLoading && (
          <EmptyState title="Queue empty" description="Promotion decisions appear when items need review." />
        )}
        <ul className="ol-ws-list">
          {(queue.data ?? []).map((item) => (
            <li key={`${item.subject_type}-${item.subject_id}`} className="ol-ws-row">
              <span className="ol-id">{item.subject_type}</span>
              {item.subject_id.slice(0, 8)}…
              {item.decided ? (
                <StatusBadge status={item.decision ?? "DECIDED"} />
              ) : (
                <StatusBadge status="PENDING" />
              )}
            </li>
          ))}
        </ul>
      </Panel>
    </StageWorkspaceFrame>
  );
}
