"use client";

import { EmptyState, Panel } from "@/components/primitives";
import { isApiError } from "@/src/api/client";
import { useLatestImpact } from "@/src/api/hooks/use-drill-queries";

export function ImpactWorkspacePanel({ cycleId }: { cycleId: string }) {
  const impact = useLatestImpact(cycleId);
  const notFound = impact.isError && isApiError(impact.error) && impact.error.status === 404;
  const itemsByType = (impact.data?.items_by_type ?? {}) as Record<string, Record<string, unknown>[]>;

  return (
    <Panel title="Impact assessment" sub="GET impact-assessments/latest">
      {impact.isLoading && <p className="ol-body-sm ol-muted">Loading…</p>}
      {notFound && (
        <EmptyState title="No impact assessment" description="Run impact analysis for this cycle." />
      )}
      {impact.data && (
        <>
          <p className="ol-body-sm">{String(impact.data.summary ?? "")}</p>
          {Boolean(impact.data.architecture_delta_suggested) && (
            <p className="ol-body-sm text-[var(--warning)]">Architecture delta suggested.</p>
          )}
          {Object.entries(itemsByType).map(([type, items]) => (
            <div key={type} className="mb-3">
              <h4 className="ol-label">{type}</h4>
              <ul className="ol-ws-bullets">
                {items.map((it, i) => (
                  <li key={i}>
                    {String(it.ref ?? it.path ?? "—")}
                    {it.impact_kind != null && (
                      <span className="ol-muted"> ({String(it.impact_kind)})</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </>
      )}
    </Panel>
  );
}
