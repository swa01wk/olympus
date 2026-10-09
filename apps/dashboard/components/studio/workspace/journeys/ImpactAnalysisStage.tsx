"use client";

import { Button, Label, Panel } from "@/components/primitives";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import { ImpactWorkspacePanel } from "@/components/studio/workspace/embed/ImpactWorkspacePanel";
import { StudioMutationAction } from "@/components/studio/workspace/StudioMutationAction";
import { previewStudioPost } from "@/lib/command-preview";
import { newIdempotencyKey } from "@/lib/utils";
import {
  declineArchitectureDelta,
  proposeArchitectureDelta,
  runImpactAssessment,
} from "@/src/api/commands";
import { isApiError } from "@/src/api/client";
import { invalidateCycleQueries, invalidateStudioCycle } from "@/src/api/hooks/invalidate-cycle";
import { useLatestImpact } from "@/src/api/hooks/use-drill-queries";
import { useActorMe, useDeliveryCycle, useInbox } from "@/src/api/hooks/use-olympus-queries";
import {
  useApprovals,
  useArchitectureDetail,
  useProjectArchitecture,
} from "@/src/api/hooks/use-studio-queries";
import { queryKeys } from "@/src/api/query-keys";
import type { ArchitectureView } from "@/src/api/types/product-model";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

type DeltaState =
  | { kind: "loading" }
  | { kind: "pending"; architectureId: string }
  | { kind: "resolved"; outcome: "approved" | "declined" }
  | { kind: "open" };

function useArchitectureDeltaState(cycleId: string, projectId: string | undefined): DeltaState {
  const inbox = useInbox({ cycleId });
  const approved = useApprovals("APPROVED");
  const latest = useProjectArchitecture(projectId);

  if (!projectId || inbox.isLoading || approved.isLoading || latest.isLoading) {
    return { kind: "loading" };
  }

  const resolvedApproval = (approved.data ?? []).find(
    (a) => a.approval_type === "ARCHITECTURE_DELTA" && a.delivery_cycle_id === cycleId,
  );
  if (resolvedApproval) {
    return {
      kind: "resolved",
      outcome:
        resolvedApproval.subject_type === "ARCHITECTURE_DELTA_DECLINED" ? "declined" : "approved",
    };
  }
  const arch = latest.data;
  if (arch?.kind === "DELTA" && arch.status === "APPROVED") {
    return { kind: "resolved", outcome: "approved" };
  }
  const pendingApproval = (inbox.data ?? []).find(
    (row) =>
      row.approval?.approval_type === "ARCHITECTURE_DELTA" &&
      row.approval.status === "PENDING" &&
      row.approval.subject_type === "architecture",
  )?.approval;
  if (pendingApproval) {
    return { kind: "pending", architectureId: pendingApproval.subject_id };
  }
  if (arch?.kind === "DELTA" && arch.status === "PROPOSED") {
    return { kind: "pending", architectureId: arch.id };
  }
  return { kind: "open" };
}

function countOf(value: unknown): number {
  return Array.isArray(value) ? value.length : 0;
}

function PendingDeltaSummary({
  architectureId,
  projectId,
}: {
  architectureId: string;
  projectId: string;
}) {
  const latest = useProjectArchitecture(projectId);
  const latestIsDelta = latest.data?.id === architectureId;
  const detail = useArchitectureDetail(latestIsDelta ? undefined : architectureId);
  const arch: ArchitectureView | null | undefined = latestIsDelta ? latest.data : detail.data;
  const body = arch?.body ?? {};
  const rationale = typeof body.rationale === "string" ? body.rationale : null;

  return (
    <div className="ol-ws-action">
      <p className="ol-body-sm" role="status">
        Delta{arch ? ` v${arch.version}` : ""} proposed, awaiting approval in the Decision panel
      </p>
      {rationale && <p className="ol-body-sm">{rationale}</p>}
      {arch && (
        <p className="ol-body-sm ol-muted">
          {countOf(body.added_components)} added components ·{" "}
          {countOf(body.changed_components)} changed components ·{" "}
          {countOf(body.changed_contracts)} changed contracts
        </p>
      )}
    </div>
  );
}

function ArchitectureDeltaSuggestedPanel({ cycleId }: { cycleId: string }) {
  const cycle = useDeliveryCycle(cycleId);
  const projectId = cycle.data?.project_id;
  const actor = useActorMe();
  const queryClient = useQueryClient();
  const canApprove = (actor.data?.roles ?? []).includes("APPROVER");
  const deltaState = useArchitectureDeltaState(cycleId, projectId);

  const [note, setNote] = useState("");
  const [declineArmed, setDeclineArmed] = useState(false);
  const [declineBusy, setDeclineBusy] = useState(false);
  const [declineError, setDeclineError] = useState<string | null>(null);
  const [declineIdem, setDeclineIdem] = useState(() => newIdempotencyKey());
  const [proposeTaskId, setProposeTaskId] = useState<string | null>(null);

  const path = `/delivery-cycles/${cycleId}/architecture-delta/decline`;
  const body = { note: note.trim() };
  const canDecline = canApprove && note.trim().length > 0;

  const invalidate = () => {
    if (projectId) invalidateStudioCycle(queryClient, { projectId, cycleId });
  };

  const confirmDecline = async () => {
    setDeclineBusy(true);
    setDeclineError(null);
    try {
      await declineArchitectureDelta(cycleId, note.trim(), declineIdem);
      setNote("");
      setDeclineArmed(false);
      invalidate();
    } catch (e) {
      setDeclineError(isApiError(e) ? e.message : e instanceof Error ? e.message : "Decline failed");
    } finally {
      setDeclineBusy(false);
    }
  };

  return (
    <Panel title="Architecture change suggested" sub="Impact assessment flagged a possible architecture delta">
      {deltaState.kind === "loading" && (
        <p className="ol-body-sm ol-muted">Loading architecture delta…</p>
      )}
      {deltaState.kind === "pending" && projectId && (
        <PendingDeltaSummary architectureId={deltaState.architectureId} projectId={projectId} />
      )}
      {deltaState.kind === "resolved" && (
        <p className="ol-body-sm" role="status">
          Architecture delta resolved ({deltaState.outcome})
        </p>
      )}
      {deltaState.kind === "open" && (
        <div className="ol-appr">
          <div className="ol-ws-action">
            <Label>Decline with note</Label>
            {!canApprove && (
              <p className="ol-body-sm ol-muted" role="status">
                You need the APPROVER role to do this.
              </p>
            )}
            <label className="ol-field">
              <span className="ol-label">Note (required)</span>
              <textarea
                rows={3}
                value={note}
                disabled={!canApprove || declineBusy}
                onChange={(ev) => setNote(ev.target.value)}
              />
            </label>
            {!declineArmed ? (
              <Button
                variant="primary"
                disabled={!canDecline || declineBusy}
                onClick={() => {
                  setDeclineIdem(newIdempotencyKey());
                  setDeclineArmed(true);
                }}
              >
                Decline with note
              </Button>
            ) : (
              <>
                <pre className="ol-cmd-api">{previewStudioPost(path, body, declineIdem)}</pre>
                <div className="ol-ws-action-row">
                  <Button disabled={declineBusy} onClick={() => setDeclineArmed(false)}>
                    Cancel
                  </Button>
                  <Button variant="primary" disabled={!canDecline || declineBusy} onClick={confirmDecline}>
                    Confirm send
                  </Button>
                </div>
              </>
            )}
            {declineError && (
              <p className="ol-body-sm ol-chat-err" role="alert">
                {declineError}
              </p>
            )}
          </div>
          <div className="ol-ws-action">
            {proposeTaskId ? (
              <p className="ol-body-sm ol-muted" role="status">
                Atlas is proposing a delta (task {proposeTaskId}). It will show here for approval once
                it lands.
              </p>
            ) : (
              <StudioMutationAction
                label="Propose a delta"
                path={`/delivery-cycles/${cycleId}/architecture-delta/propose`}
                onRun={async (idem) => {
                  const res = await proposeArchitectureDelta(cycleId, idem);
                  setProposeTaskId(res.architecture_delta_task_id);
                  invalidate();
                }}
              />
            )}
          </div>
        </div>
      )}
    </Panel>
  );
}

export function ImpactAnalysisStage({ cycleId }: { cycleId: string }) {
  const impact = useLatestImpact(cycleId);
  const queryClient = useQueryClient();
  const deltaSuggested =
    impact.data?.status === "COMPLETE" && Boolean(impact.data?.architecture_delta_suggested);

  return (
    <StageWorkspaceFrame>
      <StudioMutationAction
        label="Run impact assessment"
        path={`/delivery-cycles/${cycleId}/impact-assessments`}
        body={{}}
        onRun={async (idem) => {
          await runImpactAssessment(cycleId, {}, idem);
          invalidateCycleQueries(queryClient, cycleId);
          void queryClient.invalidateQueries({ queryKey: queryKeys.impactLatest(cycleId) });
        }}
      />
      {deltaSuggested && <ArchitectureDeltaSuggestedPanel cycleId={cycleId} />}
      <ImpactWorkspacePanel cycleId={cycleId} />
    </StageWorkspaceFrame>
  );
}
