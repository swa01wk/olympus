"use client";

import { AppShell } from "@/components/shell/AppShell";
import { ReconciliationRequired } from "@/components/truth/ReconciliationRequired";
import { EmptyState, Panel, StatusBadge } from "@/components/primitives";
import { useResolvedCycleId } from "@/lib/cycle-context";
import { useConnectors } from "@/src/api/hooks/use-drill-queries";
import { useDeliveryCycles, useProject } from "@/src/api/hooks/use-olympus-queries";
import { cycleMapPath } from "@/lib/cycle-url";
import { useRouter } from "next/navigation";

export function IntegrationsScreen({ projectId }: { projectId: string }) {
  const router = useRouter();
  const cycleId = useResolvedCycleId(projectId);
  const project = useProject(projectId);
  const cycles = useDeliveryCycles(projectId);
  const connectors = useConnectors();

  return (
    <AppShell
      project={project.data}
      cycles={cycles.data ?? []}
      cycleId={cycleId}
      onCycleChange={(id) => router.push(cycleMapPath(projectId, id))}
      stream={{ state: "disconnected", lastEventAt: null, lastRefreshAt: null }}
    >
      <div className="ol-screen">
        <h1 className="ol-title">Integrations</h1>
        <Panel title="Connector health" sub="Registry validate-all snapshot">
          {connectors.isLoading && <p className="text-sm ol-muted">Loading…</p>}
          {!connectors.data?.length && !connectors.isLoading && (
            <EmptyState title="No connectors" description="Connectors register at API startup." />
          )}
          <ul className="flex flex-col gap-2">
            {(connectors.data ?? []).map((c) => (
              <li key={c.name} className="flex flex-col gap-2 text-sm border border-[var(--border)] p-2 rounded">
                <div className="flex items-center gap-3">
                  <span className="font-mono">{c.name}</span>
                  <StatusBadge status={c.ok ? "PASS" : "FAIL"} />
                  <span className="ol-muted">{c.message}</span>
                </div>
                {!c.ok && (
                  <ReconciliationRequired connectorName={c.name} message={c.message || undefined} />
                )}
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </AppShell>
  );
}
