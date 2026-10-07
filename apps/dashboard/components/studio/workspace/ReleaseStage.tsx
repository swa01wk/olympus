"use client";

import { EligibilityChecklist } from "@/components/assurance/EligibilityChecklist";
import { EmptyState, KV, Panel, Sha, StatusBadge } from "@/components/primitives";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import { StudioMutationAction } from "@/components/studio/workspace/StudioMutationAction";
import { useCycleOutcome, useProjectReleases } from "@/src/api/hooks/use-drill-queries";
import {
  useCreateRelease,
  useApproveRelease,
  useExecuteRelease,
} from "@/src/api/hooks/use-studio-mutations";
import {
  useReleaseEligibility,
  useReleaseManifest,
  useReleaseDetail,
} from "@/src/api/hooks/use-studio-queries";
import { approveRelease, createRelease, executeRelease } from "@/src/api/commands";
import { isApiError } from "@/src/api/client";
import { useMemo, useState } from "react";

export function ReleaseStage({ projectId, cycleId }: { projectId: string; cycleId: string }) {
  const scope = { projectId, cycleId };
  const eligibility = useReleaseEligibility(cycleId);
  const releases = useProjectReleases(projectId);
  const cycleReleases = useMemo(
    () => (releases.data ?? []).filter((r) => r.delivery_cycle_id === cycleId),
    [releases.data, cycleId],
  );
  const [selectedReleaseId, setSelectedReleaseId] = useState<string | undefined>();
  const activeReleaseId = selectedReleaseId ?? cycleReleases[0]?.id;
  const release = useReleaseDetail(activeReleaseId);
  const manifest = useReleaseManifest(activeReleaseId);
  const outcome = useCycleOutcome(cycleId);
  const create = useCreateRelease(scope);
  const approve = useApproveRelease(scope);
  const execute = useExecuteRelease(scope);

  return (
    <StageWorkspaceFrame>
      <Panel title="Release eligibility" sub={`GET /delivery-cycles/${cycleId}/release-eligibility`}>
        {eligibility.isLoading && <p className="ol-body-sm ol-muted">Loading…</p>}
        {eligibility.data && (
          <EligibilityChecklist
            eligible={eligibility.data.eligible}
            conditions={eligibility.data.conditions}
          />
        )}
        <StudioMutationAction
          label="Create release"
          path={`/delivery-cycles/${cycleId}/release`}
          disabled={create.isPending}
          onRun={(idem) => createRelease(cycleId, idem)}
        />
      </Panel>
      <Panel title="Releases" sub="Approve (manifest-bound) then execute when APPROVED">
        {cycleReleases.length === 0 && (
          <EmptyState title="No release" description="Create a release when eligibility allows." />
        )}
        <ul className="ol-ws-list">
          {cycleReleases.map((r) => (
            <li key={r.id}>
              <button
                type="button"
                className={`ol-ws-list-btn ${activeReleaseId === r.id ? "is-on" : ""}`}
                onClick={() => setSelectedReleaseId(r.id)}
              >
                <span className="ol-id">{r.key}</span> <StatusBadge status={r.status} />
              </button>
            </li>
          ))}
        </ul>
        {release.data && (
          <div className="ol-ws-release-detail">
            <KV
              rows={[
                ["Status", release.data.status],
                ["Integrated SHA", release.data.integrated_sha?.slice(0, 12) ?? "—"],
              ]}
            />
            <StudioMutationAction
              label="Approve release"
              path={`/releases/${release.data.id}/approve`}
              disabled={approve.isPending}
              onRun={(idem) => approveRelease(release.data!.id, idem)}
            />
            <StudioMutationAction
              label="Execute release"
              path={`/releases/${release.data.id}/execute`}
              disabled={execute.isPending || release.data.status !== "APPROVED"}
              onRun={(idem) => executeRelease(release.data!.id, idem)}
            />
          </div>
        )}
        {manifest.data && (
          <Panel title="Manifest" sub="Hash-bound approval target">
            <p className="ol-body-sm">
              Hash: <Sha value={manifest.data.content_hash} />
            </p>
            <pre className="ol-ws-pre ol-body-sm">
              {JSON.stringify(manifest.data.content, null, 2)}
            </pre>
          </Panel>
        )}
      </Panel>
      {outcome.isError && isApiError(outcome.error) && outcome.error.status === 404 ? (
        <EmptyState title="No delivery outcome" description="Recorded when the cycle completes." />
      ) : outcome.data ? (
        <Panel title="Outcome" sub={outcome.data.result}>
          <KV rows={[["Result", outcome.data.result]]} />
        </Panel>
      ) : null}
    </StageWorkspaceFrame>
  );
}
