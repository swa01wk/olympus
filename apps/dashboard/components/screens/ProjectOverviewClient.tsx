"use client";

import { AttentionStrip } from "@/components/cycle/AttentionStrip";
import { EmptyState, KV, Panel, Sha, StatusBadge } from "@/components/primitives";
import { AppShell } from "@/components/shell/AppShell";
import { useOperatorDialogs } from "@/components/providers/OperatorDialogsProvider";
import { cycleMapPath } from "@/lib/cycle-url";
import { screenHref } from "@/lib/nav-hrefs";
import { coverageRowsForDisplay } from "@/lib/coverage-display";
import { useProjectCoverage } from "@/src/api/hooks/use-drill-queries";
import {
  useAttentionQueue,
  useDeliveryCycle,
  useDeliveryCycles,
  useProject,
  useProjectOverview,
} from "@/src/api/hooks/use-olympus-queries";
import Link from "next/link";
import { useRouter } from "next/navigation";

export function ProjectOverviewClient({ projectId }: { projectId: string }) {
  const router = useRouter();
  const operator = useOperatorDialogs();
  const project = useProject(projectId);
  const cycles = useDeliveryCycles(projectId);
  const overview = useProjectOverview(projectId);
  const coverage = useProjectCoverage(projectId);

  const activeCycleId =
    (overview.data?.active_cycle_id as string | undefined) ?? cycles.data?.[0]?.id;
  const activeCycle = useDeliveryCycle(activeCycleId);
  const attention = useAttentionQueue(activeCycleId);

  const onCycleChange = (id: string) => router.push(cycleMapPath(projectId, id));

  return (
    <AppShell
      project={project.data}
      cycles={cycles.data ?? []}
      cycleId={activeCycleId ?? ""}
      onCycleChange={onCycleChange}
      stream={{ state: "disconnected", lastEventAt: null, lastRefreshAt: null }}
    >
      <div className="ol-screen">
        <h1 className="ol-title">{project.data?.name ?? "Project overview"}</h1>
        <p className="text-sm ol-muted">S01 — persistent project truth and next decision</p>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Panel title="Released baseline" sub="Production SHA">
            {overview.data?.released_commit ? (
              <Sha value={overview.data.released_commit as string} />
            ) : (
              <span className="text-sm ol-muted">None recorded</span>
            )}
          </Panel>
          <Panel title="Canonical assurance" sub="Structural index target">
            {overview.data?.canonical_commit ? (
              <Sha value={overview.data.canonical_commit as string} />
            ) : (
              <span className="text-sm ol-muted">Not indexed</span>
            )}
          </Panel>
          <Panel title="Active cycle" sub="Current objective">
            {activeCycleId ? (
              <>
                <Link className="ol-idlink" href={cycleMapPath(projectId, activeCycleId)}>
                  Open control-plane map →
                </Link>
                <p className="text-sm mt-2">{activeCycle.data?.objective}</p>
                {activeCycle.data && <StatusBadge status={activeCycle.data.state} />}
              </>
            ) : (
              <EmptyState title="No cycle" description="Create a delivery cycle via the Control API." />
            )}
          </Panel>
          <Panel title="Coverage" sub="Named denominators only">
            {coverage.isLoading && <p className="text-sm ol-muted">Loading…</p>}
            {coverage.data && (
              <div className="flex flex-col gap-1 text-sm">
                <KV rows={coverageRowsForDisplay(coverage.data as Record<string, unknown>)} />
              </div>
            )}
          </Panel>
        </div>

        {activeCycle.data && (
          <AttentionStrip
            cycle={activeCycle.data}
            items={attention}
            onInspect={(item) => {
              operator.openAttentionItem(item);
              router.push(cycleMapPath(projectId, activeCycleId!));
            }}
            onWhy={() => router.push(cycleMapPath(projectId, activeCycleId!))}
          />
        )}

        <Panel title="Delivery cycles" sub="Continuity — every cycle and outcome">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left ol-muted">
                <th className="p-2">Key</th>
                <th className="p-2">Type</th>
                <th className="p-2">State</th>
                <th className="p-2">Map</th>
              </tr>
            </thead>
            <tbody>
              {(cycles.data ?? []).map((c) => (
                <tr key={c.id} className="border-t border-[var(--border)]">
                  <td className="p-2 font-mono">{c.key}</td>
                  <td className="p-2">{c.type}</td>
                  <td className="p-2">
                    <StatusBadge status={c.state} />
                  </td>
                  <td className="p-2">
                    <Link className="ol-idlink" href={cycleMapPath(projectId, c.id)}>
                      Map
                    </Link>
                    {" · "}
                    <Link className="ol-idlink" href={screenHref("S10", projectId, c.id)}>
                      Outcome
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>
    </AppShell>
  );
}
