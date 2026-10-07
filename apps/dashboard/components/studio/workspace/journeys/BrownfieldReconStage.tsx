"use client";

import { EmptyState, Panel, Sha } from "@/components/primitives";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import { CodeIntelligenceWorkspacePanel } from "@/components/studio/workspace/embed/CodeIntelligenceWorkspacePanel";
import { useBrownfieldDiscovery } from "@/src/api/hooks/use-journey-queries";
import { isApiError } from "@/src/api/client";

export function BrownfieldReconStage({
  projectId,
  cycleId,
}: {
  projectId: string;
  cycleId: string;
}) {
  const discovery = useBrownfieldDiscovery(cycleId);
  const notFound =
    discovery.isError && isApiError(discovery.error) && discovery.error.status === 404;

  return (
    <StageWorkspaceFrame>
      <Panel title="Repository discovery" sub={`GET /delivery-cycles/${cycleId}/discovery`}>
        {discovery.isLoading && <p className="ol-body-sm ol-muted">Loading…</p>}
        {notFound && (
          <EmptyState title="No discovery record" description="Discovery runs during RECON." />
        )}
        {discovery.data && (
          <>
            <p className="ol-body-sm">
              Commit <Sha value={discovery.data.commit_sha} /> · hash{" "}
              <Sha value={discovery.data.content_hash} />
            </p>
            <pre className="ol-ws-pre">{JSON.stringify(discovery.data.content, null, 2)}</pre>
          </>
        )}
      </Panel>
      <CodeIntelligenceWorkspacePanel projectId={projectId} cycleId={cycleId} />
    </StageWorkspaceFrame>
  );
}
