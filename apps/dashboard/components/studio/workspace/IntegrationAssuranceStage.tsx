"use client";

import { EvidenceMatrix } from "@/components/assurance/EvidenceMatrix";
import { Panel, Sha, StatusBadge } from "@/components/primitives";
import { ProvisionalBaselinesPanel } from "@/components/studio/ProvisionalBaselinesPanel";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import { StudioMutationAction } from "@/components/studio/workspace/StudioMutationAction";
import { findingBlockingLabel, findingCodeLocation } from "@/lib/finding-location";
import { remediateFinding, waiveFinding } from "@/src/api/commands";
import { invalidateStudioCycle } from "@/src/api/hooks/invalidate-cycle";
import { useCycleFindings } from "@/src/api/hooks/use-journey-queries";
import { useIcAssurance } from "@/src/api/hooks/use-drill-queries";
import { useInbox, useIntegrationCandidates } from "@/src/api/hooks/use-olympus-queries";
import type { InboxItem } from "@/src/api/types/core";
import type { CycleFinding } from "@/src/api/types/journey";
import { useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";

function pendingWaiverFindingIds(inbox: InboxItem[]): Set<string> {
  const ids = new Set<string>();
  for (const row of inbox) {
    const a = row.approval;
    if (
      a &&
      a.approval_type === "FINDING_WAIVER" &&
      a.subject_type === "FINDING" &&
      a.status === "PENDING"
    ) {
      ids.add(a.subject_id);
    }
  }
  return ids;
}

function FindingRow({
  finding,
  cycleId,
  projectId,
  waiverPending,
}: {
  finding: CycleFinding;
  cycleId: string;
  projectId: string;
  waiverPending: boolean;
}) {
  const queryClient = useQueryClient();
  const { file, line } = findingCodeLocation(finding);
  const blockingLabel = findingBlockingLabel(finding);
  const open = finding.status === "OPEN";
  const actionable = open && !waiverPending;

  const invalidate = () => {
    invalidateStudioCycle(queryClient, { projectId, cycleId });
  };

  return (
    <li className="ol-ws-row ol-appr">
      <div className="ol-ws-action-row">
        <span className="ol-id">{finding.key}</span>
        <StatusBadge status={finding.status} />
        <span className="ol-body-sm">{finding.severity}</span>
        <span className="ol-body-sm ol-muted">{finding.category}</span>
      </div>
      <p className="ol-body-sm">{finding.title}</p>
      {(file || line != null) && (
        <p className="ol-body-sm ol-muted">
          {file ?? "—"}
          {line != null ? `:${line}` : ""}
        </p>
      )}
      {blockingLabel && (
        <p className="ol-body-sm" role="status">
          {blockingLabel}
        </p>
      )}
      {open && waiverPending && (
        <p className="ol-body-sm ol-muted" role="status">
          Waiver pending approval
        </p>
      )}
      {actionable && (
        <div className="ol-ws-action-row">
          <StudioMutationAction
            label="Waive"
            path={`/findings/${finding.id}/waive`}
            onRun={async (idem) => {
              await waiveFinding(finding.id, idem);
              invalidate();
            }}
          />
          {finding.blocking && (
            <StudioMutationAction
              label="Remediate"
              path={`/findings/${finding.id}/remediate`}
              onRun={async (idem) => {
                await remediateFinding(finding.id, idem);
                invalidate();
              }}
            />
          )}
        </div>
      )}
    </li>
  );
}

/** Embedded assurance view (S09) for INTEGRATION and ASSURANCE stages. */
export function IntegrationAssuranceStage({
  projectId,
  cycleId,
  stage,
}: {
  projectId: string;
  cycleId: string;
  stage: string;
}) {
  const ics = useIntegrationCandidates(cycleId);
  const ic = ics.data?.[ics.data.length - 1];
  const assurance = useIcAssurance(ic?.id);
  const findings = useCycleFindings(cycleId);
  const inbox = useInbox({ cycleId });
  const pendingWaivers = useMemo(() => pendingWaiverFindingIds(inbox.data ?? []), [inbox.data]);

  const data = assurance.data ?? {};
  const obligations = (data.obligations as Record<string, unknown>[]) ?? [];
  const evidence = (data.evidence as Record<string, unknown>[]) ?? [];
  const coverage = (data.coverage as Record<string, unknown>[]) ?? [];
  const targetSha = ic?.integrated_sha ?? ic?.base_sha;

  return (
    <StageWorkspaceFrame>
      <Panel
        title={stage === "INTEGRATION" ? "Integration" : "Assurance"}
        sub="Integration candidate and evidence matrix"
      >
        {ic && (
          <p className="ol-body-sm mb-3">
            Target: {targetSha ? <Sha value={targetSha} /> : "—"} · IC {ic.key}
          </p>
        )}
        {!ic && (
          <p className="ol-body-sm ol-muted">No integration candidate yet for this cycle.</p>
        )}
        {assurance.isLoading && <p className="ol-body-sm ol-muted">Loading assurance view…</p>}
        <EvidenceMatrix
          obligations={obligations}
          evidence={evidence}
          coverage={coverage}
          targetSha={targetSha}
        />
      </Panel>
      <Panel title="Findings" sub={`GET /delivery-cycles/${cycleId}/findings`}>
        {findings.isLoading && <p className="ol-body-sm ol-muted">Loading findings…</p>}
        {(findings.data ?? []).length === 0 && !findings.isLoading && (
          <p className="ol-body-sm ol-muted">No findings for this cycle.</p>
        )}
        <ul className="ol-ws-list">
          {(findings.data ?? []).map((finding) => (
            <FindingRow
              key={finding.id}
              finding={finding}
              cycleId={cycleId}
              projectId={projectId}
              waiverPending={pendingWaivers.has(finding.id)}
            />
          ))}
        </ul>
      </Panel>
      <ProvisionalBaselinesPanel projectId={projectId} />
    </StageWorkspaceFrame>
  );
}
