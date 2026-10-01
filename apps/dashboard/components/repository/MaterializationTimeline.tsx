"use client";

import type { RepositoryMaterialization } from "@/lib/contracts/entity-types";
import { Panel } from "@/components/design/Panel";

export function MaterializationTimeline({
  materializations,
}: {
  materializations: RepositoryMaterialization[];
}) {
  if (materializations.length === 0) {
    return (
      <Panel title="Materialization" stateRail="neutral">
        <p className="text-xs text-[var(--muted)]">No materialization attempts recorded.</p>
      </Panel>
    );
  }

  return (
    <Panel title="Materialization timeline" stateRail="neutral">
      <ul className="space-y-3 text-xs">
        {materializations.map((m) => (
          <li key={m.id} className="rounded border border-[var(--border)] p-2">
            <div className="font-mono text-amber-200">
              {m.kind} · attempt {m.attempt} · {m.status}
            </div>
            {m.progress && (
              <div className="mt-1 text-[var(--muted)]">
                Objects {m.progress.objects_received ?? 0}/{m.progress.objects_total ?? "?"} · bytes{" "}
                {m.progress.bytes_received ?? 0}
              </div>
            )}
            <ol className="mt-2 list-inside list-decimal">
              {m.steps?.map((s) => (
                <li key={s.step_key}>
                  {s.label} — {s.status}
                </li>
              ))}
            </ol>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
