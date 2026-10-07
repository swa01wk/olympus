"use client";

import { EmptyState, Panel, Sha, StatusBadge } from "@/components/primitives";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import { useReadinessAssessment } from "@/src/api/hooks/use-journey-queries";

export function BrownfieldReadinessStage({ cycleId }: { cycleId: string }) {
  const readiness = useReadinessAssessment(cycleId);

  return (
    <StageWorkspaceFrame>
      <Panel title="Readiness" sub={`GET /delivery-cycles/${cycleId}/readiness`}>
        {readiness.isLoading && <p className="ol-body-sm ol-muted">Loading…</p>}
        {!readiness.data && !readiness.isLoading && (
          <EmptyState title="No assessment" description="Readiness is computed at this stage." />
        )}
        {readiness.data && (
          <>
            <p className="ol-body-sm">
              <StatusBadge status={readiness.data.result} /> · commit{" "}
              <Sha value={readiness.data.commit_sha} />
            </p>
            <ul className="ol-ws-bullets">
              {readiness.data.reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
            <pre className="ol-ws-pre">{JSON.stringify(readiness.data.metrics, null, 2)}</pre>
          </>
        )}
      </Panel>
    </StageWorkspaceFrame>
  );
}
