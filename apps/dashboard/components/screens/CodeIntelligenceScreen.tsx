"use client";

import { ShaScopeBanner } from "@/components/code/ShaScopeBanner";
import { CycleDrillFrame } from "@/components/cycle/CycleDrillFrame";
import { EmptyState, KV, Panel } from "@/components/primitives";
import { useResolvedCycleId } from "@/lib/cycle-context";
import { useProjectRepositoryView } from "@/src/api/hooks/use-drill-queries";
import {
  useDeliveryCycle,
  useIntegrationCandidates,
  useProjectOverview,
} from "@/src/api/hooks/use-olympus-queries";

export function CodeIntelligenceScreen({ projectId }: { projectId: string }) {
  const cycleId = useResolvedCycleId(projectId);
  const overview = useProjectOverview(projectId);
  const repoView = useProjectRepositoryView(projectId);
  const cycle = useDeliveryCycle(cycleId || undefined);
  const ics = useIntegrationCandidates(cycleId || undefined);

  const repo = repoView.data?.repository as Record<string, unknown> | null | undefined;
  const ic = ics.data?.[ics.data.length - 1];

  return (
    <CycleDrillFrame projectId={projectId} cycleId={cycleId} activeScreen="S06">
      <ShaScopeBanner
        provisional={ic?.integrated_sha ?? cycle.data?.base_sha}
        canonical={(overview.data?.canonical_commit as string) ?? (repo?.canonical_commit as string)}
        released={(overview.data?.released_commit as string) ?? (repo?.released_commit as string)}
      />
      <Panel title="S06 · Code intelligence" sub="Structural truth — scopes labelled separately">
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
    </CycleDrillFrame>
  );
}
