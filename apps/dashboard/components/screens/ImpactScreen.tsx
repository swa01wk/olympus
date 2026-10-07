"use client";

import { CycleDrillFrame } from "@/components/cycle/CycleDrillFrame";
import { EmptyState, Panel } from "@/components/primitives";
import { useLatestImpact } from "@/src/api/hooks/use-drill-queries";
import { cycleMapPath } from "@/lib/cycle-url";
import Link from "next/link";
import { isApiError } from "@/src/api/client";

export function ImpactScreen({ projectId, cycleId }: { projectId: string; cycleId: string }) {
  const impact = useLatestImpact(cycleId);
  const notFound = impact.isError && isApiError(impact.error) && impact.error.status === 404;
  const itemsByType = (impact.data?.items_by_type ?? {}) as Record<string, Record<string, unknown>[]>;

  return (
    <CycleDrillFrame projectId={projectId} cycleId={cycleId} activeScreen="S08">
      <Panel title="S08 · Impact explorer" sub="Impact lens — FACT vs INFERENCE">
        {impact.isLoading && <p className="text-sm ol-muted">Loading assessment…</p>}
        {notFound && (
          <EmptyState
            title="No impact assessment"
            description="Impact analysis has not been recorded for this cycle yet."
          />
        )}
        {impact.data && (
          <>
            <p className="text-sm mb-2">{String(impact.data.summary ?? "")}</p>
            {Boolean(impact.data.architecture_delta_suggested) && (
              <p className="text-sm text-[var(--warning)] mb-3">Architecture delta suggested — review before execution.</p>
            )}
            {Object.entries(itemsByType).map(([type, items]) => (
              <div key={type} className="mb-4">
                <h3 className="ol-insp-st">{type}</h3>
                <ul className="text-sm flex flex-col gap-1">
                  {items.map((it, i) => (
                    <li key={i} className="border border-[var(--border)] rounded p-2">
                      <span className="font-mono text-xs">{String(it.ref ?? it.path ?? "—")}</span>
                      {it.impact_kind != null && (
                        <span className="ml-2 ol-muted">({String(it.impact_kind)})</span>
                      )}
                      {it.confidence != null && (
                        <span className="ml-2 ol-muted">conf {String(it.confidence)}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </>
        )}
        <Link className="ol-idlink text-sm" href={cycleMapPath(projectId, cycleId, { lens: "impact" })}>
          Show on map (impact lens) →
        </Link>
      </Panel>
    </CycleDrillFrame>
  );
}
