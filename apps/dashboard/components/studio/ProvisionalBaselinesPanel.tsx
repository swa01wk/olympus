"use client";

import { Panel } from "@/components/primitives";
import { useProjectBaselines } from "@/src/api/hooks/use-journey-queries";

export function ProvisionalBaselinesPanel({ projectId }: { projectId: string }) {
  const baselines = useProjectBaselines(projectId);
  const provisional = (baselines.data ?? []).filter((b) => b.provisional);
  if (baselines.isLoading || provisional.length === 0) {
    return null;
  }
  return (
    <Panel title="Provisional baselines" sub="Rest on accepted known gaps — gate failures are reported, not blocking">
      <ul className="ol-ws-list">
        {provisional.map((b) => {
          const gaps = b.provisional_known_gaps ?? [];
          return (
            <li key={b.id} className="ol-ws-row">
              <span className="ol-chip ol-tone-neutral">Provisional</span>
              <span className="ol-id">{b.lineage_key}</span>
              <span className="ol-body-sm ol-muted">v{b.version} · {b.status}</span>
              <span className="ol-body-sm ol-muted">{b.check_ref}</span>
              <div className="ol-ws-row-detail">
                <span className="ol-label">Known gap{gaps.length === 1 ? "" : "s"}</span>
                {gaps.length > 0 ? (
                  <ul className="ol-ws-bullets">
                    {gaps.map((g) => (
                      <li key={g}>{g}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="ol-body-sm ol-muted">Known gap not recorded.</p>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
