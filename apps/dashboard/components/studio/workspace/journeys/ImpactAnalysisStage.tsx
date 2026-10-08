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
import { invalidateStudioCycle } from "@/src/api/hooks/invalidate-cycle";
import { useLatestImpact } from "@/src/api/hooks/use-drill-queries";
import { useActorMe, useDeliveryCycle } from "@/src/api/hooks/use-olympus-queries";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

function ArchitectureDeltaSuggestedPanel({ cycleId }: { cycleId: string }) {
  const cycle = useDeliveryCycle(cycleId);
  const actor = useActorMe();
  const queryClient = useQueryClient();
  const canApprove = (actor.data?.roles ?? []).includes("APPROVER");

  const [note, setNote] = useState("");
  const [declineArmed, setDeclineArmed] = useState(false);
  const [declineBusy, setDeclineBusy] = useState(false);
  const [declineError, setDeclineError] = useState<string | null>(null);
  const [declineIdem, setDeclineIdem] = useState(() => newIdempotencyKey());

  const path = `/delivery-cycles/${cycleId}/architecture-delta/decline`;
  const body = { note: note.trim() };
  const canDecline = canApprove && note.trim().length > 0;

  const invalidate = () => {
    const projectId = cycle.data?.project_id;
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
          <StudioMutationAction
            label="Propose a delta"
            path={`/delivery-cycles/${cycleId}/architecture-delta/propose`}
            onRun={async (idem) => {
              await proposeArchitectureDelta(cycleId, idem);
              invalidate();
            }}
          />
          <p className="ol-body-sm ol-muted">
            Atlas will propose a delta, but it can&apos;t be approved until the backend persists deltas
            (plan G11, phase RL2).
          </p>
        </div>
      </div>
    </Panel>
  );
}

export function ImpactAnalysisStage({ cycleId }: { cycleId: string }) {
  const impact = useLatestImpact(cycleId);
  const deltaSuggested = Boolean(impact.data?.architecture_delta_suggested);

  return (
    <StageWorkspaceFrame>
      <StudioMutationAction
        label="Run impact assessment"
        path={`/delivery-cycles/${cycleId}/impact-assessments`}
        body={{}}
        onRun={async (idem) => {
          await runImpactAssessment(cycleId, {}, idem);
        }}
      />
      {deltaSuggested && <ArchitectureDeltaSuggestedPanel cycleId={cycleId} />}
      <ImpactWorkspacePanel cycleId={cycleId} />
    </StageWorkspaceFrame>
  );
}
