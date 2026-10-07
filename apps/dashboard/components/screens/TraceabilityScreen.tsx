"use client";

import { CycleDrillFrame } from "@/components/cycle/CycleDrillFrame";
import { EmptyState, Panel } from "@/components/primitives";
import { useResolvedCycleId } from "@/lib/cycle-context";
import { useFeatureLineage, useProjectFeatures } from "@/src/api/hooks/use-drill-queries";
import { cycleMapPath } from "@/lib/cycle-url";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

export function TraceabilityScreen({ projectId }: { projectId: string }) {
  const cycleId = useResolvedCycleId(projectId);
  const searchParams = useSearchParams();
  const featureId = searchParams.get("feature") ?? undefined;
  const features = useProjectFeatures(projectId);
  const lineage = useFeatureLineage(featureId);

  const selectedFeature = features.data?.find((f) => f.id === featureId);

  return (
    <CycleDrillFrame projectId={projectId} cycleId={cycleId} activeScreen="S07">
      <Panel title="S07 · Traceability" sub="Trace lens — lineage with origin labels">
        <p className="text-sm ol-muted mb-3">
          Pick a feature to load forward lineage. Historical and inferred links stay visible with labels.
        </p>
        <div className="flex flex-wrap gap-2 mb-4">
          {(features.data ?? []).map((f) => (
            <Link
              key={f.id}
              className={`ol-back ${featureId === f.id ? "border-[var(--active)]" : ""}`}
              href={`/projects/${projectId}/lineage?cycle=${cycleId}&feature=${f.id}`}
            >
              {f.key}
            </Link>
          ))}
        </div>
        {!featureId && (
          <EmptyState title="Select a feature" description="Choose a feature chip above." />
        )}
        {selectedFeature && (
          <p className="text-sm mb-2">
            <strong>{selectedFeature.name}</strong>
          </p>
        )}
        {lineage.isLoading && featureId && <p className="ol-muted text-sm">Loading lineage…</p>}
        {lineage.data && (
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <h3 className="ol-insp-st">Nodes ({lineage.data.nodes.length})</h3>
              <ul className="text-xs font-mono max-h-64 overflow-auto">
                {lineage.data.nodes.map((n, i) => (
                  <li key={i}>{JSON.stringify(n)}</li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="ol-insp-st">Edges ({lineage.data.edges.length})</h3>
              <ul className="text-xs font-mono max-h-64 overflow-auto">
                {lineage.data.edges.map((e, i) => (
                  <li key={i}>{JSON.stringify(e)}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
        {cycleId && (
          <Link className="ol-idlink text-sm" href={cycleMapPath(projectId, cycleId, { lens: "trace" })}>
            Show on map (trace lens) →
          </Link>
        )}
      </Panel>
    </CycleDrillFrame>
  );
}
