"use client";

import { CycleDrillFrame } from "@/components/cycle/CycleDrillFrame";
import { EmptyState, Panel, ProvenanceBadge } from "@/components/primitives";
import { useResolvedCycleId } from "@/lib/cycle-context";
import { useCycleKnowledge, useProjectFeatures } from "@/src/api/hooks/use-drill-queries";
import { useDeliveryCycle } from "@/src/api/hooks/use-olympus-queries";

export function ProductSpecsScreen({ projectId }: { projectId: string }) {
  const cycleId = useResolvedCycleId(projectId);
  const cycle = useDeliveryCycle(cycleId || undefined);
  const features = useProjectFeatures(projectId);
  const knowledge = useCycleKnowledge(cycleId || undefined);

  const journey = cycle.data?.type;

  return (
    <CycleDrillFrame projectId={projectId} cycleId={cycleId} activeScreen="S03">
      <Panel title="S03 · Product / specs" sub="Intent lane — behavioural vs implementation truth">
        {journey === "BROWNFIELD_ONBOARDING" && (
          <p className="text-sm ol-muted mb-3">
            Brownfield mode: recovered intent stays proposed until reviewed and promoted.
          </p>
        )}
        {journey === "BUG_FIX" && (
          <p className="text-sm ol-muted mb-3">Bug fix: compare observed vs expected behaviour with sources.</p>
        )}
      </Panel>
      <div className="grid gap-4 md:grid-cols-2">
        <Panel title="Features" sub="Capability tree entry points">
          {features.isLoading && <p className="ol-muted text-sm">Loading…</p>}
          {!features.isLoading && !features.data?.length && (
            <EmptyState title="No features" description="Define product model via Control API." />
          )}
          <ul className="flex flex-col gap-2">
            {(features.data ?? []).map((f) => (
              <li key={f.id} className="text-sm border border-[var(--border)] rounded p-2">
                <span className="font-mono text-xs">{f.key}</span> — {f.name}
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Cycle knowledge" sub="Provenance-classified statements">
          <ul className="flex flex-col gap-2">
            {(knowledge.data ?? []).map((k) => (
              <li key={k.id} className="text-sm">
                <ProvenanceBadge kind={(k.class as "FACT" | "INFERENCE" | "UNCERTAINTY" | "ASSUMPTION" | "DECISION") ?? "ASSUMPTION"} />
                <span className="ml-2">{k.statement}</span>
              </li>
            ))}
            {!knowledge.data?.length && (
              <p className="text-sm ol-muted">No knowledge items for this cycle.</p>
            )}
          </ul>
        </Panel>
      </div>
    </CycleDrillFrame>
  );
}
