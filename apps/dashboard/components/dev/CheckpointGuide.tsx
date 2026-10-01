"use client";

import type { ScenarioCheckpointMeta } from "@/lib/api/scenario-controller";

export function CheckpointGuide({ meta }: { meta: ScenarioCheckpointMeta }) {
  return (
    <div className="text-xs text-[var(--muted)]">
      <span className="text-[var(--foreground)]">{meta.narrative}</span>
      {meta.lookAt.length > 0 && (
        <span className="ml-2">
          Where to look:{" "}
          {meta.lookAt.map((label, i) => (
            <span key={label}>
              {i > 0 ? " · " : ""}
              <span className="text-amber-200/90">{label}</span>
            </span>
          ))}
        </span>
      )}
    </div>
  );
}
