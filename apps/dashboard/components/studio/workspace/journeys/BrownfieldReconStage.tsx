"use client";

import { EmptyState, Panel, Sha } from "@/components/primitives";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import { CodeIntelligenceWorkspacePanel } from "@/components/studio/workspace/embed/CodeIntelligenceWorkspacePanel";
import { useBrownfieldDiscovery, useRepository } from "@/src/api/hooks/use-journey-queries";
import { isApiError } from "@/src/api/client";

export function BrownfieldReconStage({
  projectId,
  cycleId,
  repositoryId,
}: {
  projectId: string;
  cycleId: string;
  repositoryId: string | null;
}) {
  const discovery = useBrownfieldDiscovery(cycleId);
  const repository = useRepository(repositoryId ?? undefined);
  const notFound =
    discovery.isError && isApiError(discovery.error) && discovery.error.status === 404;

  return (
    <StageWorkspaceFrame>
      {repositoryId && (
        <Panel title="Repository" sub={`GET /repositories/${repositoryId}`}>
          {repository.isLoading && !repository.data && (
            <p className="ol-body-sm ol-muted">Loading repository…</p>
          )}
          {repository.data && (
            <dl className="ol-appr-scope">
              <div>
                <dt className="ol-label">Provider</dt>
                <dd>{repository.data.provider}</dd>
              </div>
              <div>
                <dt className="ol-label">Remote URL</dt>
                <dd className="ol-body-sm">{repository.data.remote_url ?? "—"}</dd>
              </div>
              <div>
                <dt className="ol-label">Default branch</dt>
                <dd>{repository.data.default_branch}</dd>
              </div>
              <div>
                <dt className="ol-label">Canonical commit</dt>
                <dd>
                  <Sha
                    value={
                      repository.data.canonical_commit ??
                      repository.data.registered_sha ??
                      "—"
                    }
                  />
                </dd>
              </div>
              <div>
                <dt className="ol-label">Status</dt>
                <dd>{repository.data.status}</dd>
              </div>
            </dl>
          )}
        </Panel>
      )}
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
