"use client";

import { Panel } from "@/components/primitives";
import {
  parseChangesRequestedAudit,
  type AuditRow,
} from "@/lib/changes-requested-audit";
import { findChangesRequestedApprovalForStage } from "@/lib/studio-spine";
import { fetchAuditForTarget, listApprovals } from "@/src/api/resources";
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
    queryKey: ["approvals", "CHANGES_REQUESTED", cycleId],
    queryFn: () => listApprovals({ status: "CHANGES_REQUESTED" }),
  });

  const match = findChangesRequestedApprovalForStage(
    approvals.data ?? [],
    stage,
    cycleType,
    cycleId,
  );

  const audit = useQuery({
    queryKey: ["audit", "approval", match?.id ?? ""],
    queryFn: () => fetchAuditForTarget("approval", match!.id),
    enabled: Boolean(match?.id),
  });

  if (!match) return null;

  const parsed = parseChangesRequestedAudit((audit.data ?? []) as AuditRow[]);

  return (
    <Panel
      title="Changes requested"
      sub={`${match.approval_type} · ${match.subject_type}`}
      className="ol-changes-requested"
    >
      <p className="ol-body-sm ol-muted">
        Subject <span className="ol-id">{match.subject_id}</span>
      </p>
      {parsed?.note ? (
        <blockquote className="ol-body-sm">{parsed.note}</blockquote>
      ) : (
        <p className="ol-body-sm ol-muted">No note found in audit for this approval.</p>
      )}
      {parsed && (
        <p className="ol-body-sm ol-muted">
          Recorded {parsed.occurredAt} · actor <span className="ol-id">{parsed.actorId}</span>
        </p>
      )}
    </Panel>
  );
}
