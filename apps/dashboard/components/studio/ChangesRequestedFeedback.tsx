"use client";

import { Panel } from "@/components/primitives";
import { findChangesRequestedApprovalForStage } from "@/lib/studio-spine";
import { useActorMe } from "@/src/api/hooks/use-olympus-queries";
import { listApprovals } from "@/src/api/resources";
import type { DeliveryCycleType } from "@/src/control-plane/stage-lanes";
import { useQuery } from "@tanstack/react-query";

export function ChangesRequestedFeedback({
  cycleId,
  cycleType,
  stage,
}: {
  cycleId: string;
  cycleType: DeliveryCycleType;
  stage: string;
}) {
  const approvals = useQuery({
    queryKey: ["approvals", "list"],
    queryFn: () => listApprovals(),
  });
  const actor = useActorMe();

  const match = findChangesRequestedApprovalForStage(
    approvals.data ?? [],
    stage,
    cycleType,
    cycleId,
  );

  if (!match) return null;

  const authorId = match.decided_by_actor_id;
  const authorName =
    authorId && actor.data?.actor_id === authorId ? actor.data.name : null;

  return (
    <Panel
      title="Changes requested"
      sub={`${match.approval_type} · ${match.subject_type}`}
      className="ol-changes-requested"
    >
      <p className="ol-body-sm ol-muted">
        Subject <span className="ol-id">{match.subject_id}</span>
      </p>
      {match.decision_note?.trim() ? (
        <blockquote className="ol-body-sm">{match.decision_note}</blockquote>
      ) : (
        <p className="ol-body-sm ol-muted">No note was recorded for this approval.</p>
      )}
      {(match.decided_at || authorId) && (
        <p className="ol-body-sm ol-muted">
          {match.decided_at && <>Requested {match.decided_at}</>}
          {match.decided_at && authorId && " · "}
          {authorId &&
            (authorName ? (
              <>by {authorName}</>
            ) : (
              <>
                by <span className="ol-id">{authorId}</span>
              </>
            ))}
        </p>
      )}
    </Panel>
  );
}
