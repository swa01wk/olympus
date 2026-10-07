"use client";

import { ShaScopeBanner } from "@/components/code/ShaScopeBanner";
import { EmptyState, KV, Panel } from "@/components/primitives";
import { useProjectRepositoryView } from "@/src/api/hooks/use-drill-queries";
import {
  useDeliveryCycle,
  useIntegrationCandidates,
  useProjectOverview,
} from "@/src/api/hooks/use-olympus-queries";

export function CodeIntelligenceWorkspacePanel({
  projectId,
  cycleId,
}: {
  projectId: string;
  cycleId: string;
}) {
  const overview = useProjectOverview(projectId);
  const repoView = useProjectRepositoryView(projectId);
  const cycle = useDeliveryCycle(cycleId);
  const ics = useIntegrationCandidates(cycleId);
  const repo = repoView.data?.repository as Record<string, unknown> | null | undefined;
  const ic = ics.data?.[ics.data.length - 1];

  return (
    <>
      <ShaScopeBanner
        provisional={ic?.integrated_sha ?? cycle.data?.base_sha}
        canonical={(overview.data?.canonical_commit as string) ?? (repo?.canonical_commit as string)}
        released={(overview.data?.released_commit as string) ?? (repo?.released_commit as string)}
      />
      <Panel title="Repository" sub="Structural truth for this project">
        {!repo && !repoView.isLoading && (
          <EmptyState title="No repository" description="Attach a repository to this project." />
        )}
        {repo && (
          <KV
            rows={[
              ["Repository", String(repo.name)],
              ["Default branch", String(repo.default_branch ?? "—")],
              ["Status", String(repo.status)],
              ["Registered SHA", String(repo.registered_sha ?? "—")],
            ]}
          />
        )}
      </Panel>
    </>
  );
}
