"use client";

import { EmptyState, Panel, Sha, StatusBadge } from "@/components/primitives";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import { useRegisterStudioFocus } from "@/lib/studio-focus";
import { useCycleSpecDelta } from "@/src/api/hooks/use-journey-queries";
import { isApiError } from "@/src/api/client";

export function SpecDeltaStage({ cycleId }: { cycleId: string }) {
  const delta = useCycleSpecDelta(cycleId);
  const notFound = delta.isError && isApiError(delta.error) && delta.error.status === 404;
  useRegisterStudioFocus(
    delta.data ? { subject_type: "spec_delta", subject_id: delta.data.id } : null,
  );

  return (
    <StageWorkspaceFrame>
      <Panel title="Spec delta" sub={`GET /delivery-cycles/${cycleId}/spec-delta`}>
        {delta.isLoading && <p className="ol-body-sm ol-muted">Loading…</p>}
        {notFound && (
          <EmptyState title="No spec delta" description="Compute a delta after feature change intake." />
        )}
        {delta.data && (
          <>
            <p className="ol-body-sm">
              <StatusBadge status={delta.data.status} /> · <Sha value={delta.data.content_hash} />
            </p>
            <pre className="ol-ws-pre">{JSON.stringify(delta.data.changes, null, 2)}</pre>
          </>
        )}
      </Panel>
    </StageWorkspaceFrame>
  );
}
