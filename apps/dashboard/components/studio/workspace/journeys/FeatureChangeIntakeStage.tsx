"use client";

import { EmptyState, Panel, StatusBadge } from "@/components/primitives";
import { ExceptionState } from "@/components/truth/ExceptionState";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import { StudioMutationAction } from "@/components/studio/workspace/StudioMutationAction";
import { rerunChangeInterpretation } from "@/src/api/commands";
import {
  useChangeInterpretation,
  useChangeRequests,
} from "@/src/api/hooks/use-journey-queries";
import { isApiError } from "@/src/api/client";

export function FeatureChangeIntakeStage({
  projectId,
  cycleId,
}: {
  projectId: string;
  cycleId: string;
}) {
  const requests = useChangeRequests(projectId);
  const interpretation = useChangeInterpretation(cycleId);
  const forCycle = (requests.data ?? []).filter((r) => r.delivery_cycle_id === cycleId);
  const interp404 = interpretation.isError && isApiError(interpretation.error) && interpretation.error.status === 404;

  return (
    <StageWorkspaceFrame>
      <Panel title="Change requests" sub={`GET /projects/${projectId}/change-requests`}>
        {forCycle.length === 0 && !requests.isLoading && (
          <EmptyState title="No change request" description="Intake via API or chat proposal." />
        )}
        <ul className="ol-ws-list">
          {forCycle.map((r) => (
            <li key={r.id} className="ol-ws-row">
              <span className="ol-id">{r.key}</span> {r.title} <StatusBadge status={r.status} />
            </li>
          ))}
        </ul>
      </Panel>
      <Panel title="Interpretation" sub="Linked change understanding for this cycle">
        {interpretation.isLoading && <p className="ol-body-sm ol-muted">Loading…</p>}
        {interp404 && (
          <p className="ol-body-sm ol-muted">No interpretation linked to this cycle yet.</p>
        )}
        {interpretation.isError && !interp404 && (
          <ExceptionState status="ERROR" reason="Could not load interpretation." />
        )}
        {interpretation.data && (
          <pre className="ol-ws-pre">{JSON.stringify(interpretation.data, null, 2)}</pre>
        )}
        <StudioMutationAction
          label="Rerun interpretation"
          path={`/delivery-cycles/${cycleId}/change-interpretation/rerun`}
          onRun={(idem) => rerunChangeInterpretation(cycleId, idem)}
        />
      </Panel>
    </StageWorkspaceFrame>
  );
}
