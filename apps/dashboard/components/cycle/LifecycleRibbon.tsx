"use client";

import type { StageLane } from "@/src/control-plane/stage-lanes";
import { cn } from "@/lib/utils";

export function LifecycleRibbon({
  stages,
  currentIndex,
  terminalState,
}: {
  stages: StageLane[];
  currentIndex: number;
  terminalState?: string;
}) {
  return (
    <ol className="ol-ribbon" aria-label="Delivery cycle lifecycle">
      {stages.map((s, i) => {
        const state = i < currentIndex ? "done" : i === currentIndex ? "now" : "next";
        const isPast = i < currentIndex;
        return (
          <li key={s.state}>
            <button
              type="button"
              className={cn("ol-rib", `is-${state}`)}
              aria-current={i === currentIndex ? "step" : undefined}
              disabled={!isPast && i !== currentIndex}
              title={
                isPast
                  ? `${s.state} (recorded — history view unavailable)`
                  : i === currentIndex && terminalState
                    ? `${s.state} · terminal ${terminalState}`
                    : `${s.state} · ${s.laneCode} lane`
              }
            >
              <span className="ol-rib-g" aria-hidden="true">
                {state === "done" ? "✓" : state === "now" ? "●" : "○"}
              </span>
              <span className="ol-rib-k">{s.state.replace(/_/g, " ")}</span>
              <span className="ol-rib-lane">{s.laneCode}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
