"use client";

import { screenHref } from "@/lib/nav-hrefs";
import { cycleMapPath } from "@/lib/cycle-url";
import { LANES, type ScreenId } from "@/src/control-plane/lanes";
import { laneForCycleState } from "@/src/control-plane/stage-lanes";
import type { DeliveryCycle } from "@/src/api/types/core";
import Link from "next/link";
import { cn } from "@/lib/utils";

export function LaneStrip({
  projectId,
  cycleId,
  cycle,
  activeScreen,
}: {
  projectId: string;
  cycleId: string;
  cycle: DeliveryCycle;
  activeScreen: ScreenId;
}) {
  const currentLane = laneForCycleState(cycle.type, cycle.state)?.laneId;

  return (
    <div className="ol-lanestrip" aria-label="Lane drill-down">
      <Link
        className="ol-lanestrip-l ol-idlink text-xs"
        href={cycleMapPath(projectId, cycleId)}
      >
        ← Map
      </Link>
      {LANES.map((lane) => {
        const href = screenHref(lane.screen, projectId, cycleId);
        const on = activeScreen === lane.screen;
        const isNow = currentLane === lane.id;
        return (
          <Link
            key={lane.id}
            href={href}
            className={cn("ol-ls", on && "is-on", isNow && "is-now")}
            aria-current={on ? "page" : undefined}
          >
            <span className="ol-ls-code">{lane.code}</span>
            <span className="ol-ls-name">{lane.short}</span>
            <span className="ol-ls-n">{lane.screen.replace("S", "")}</span>
          </Link>
        );
      })}
      {(activeScreen === "S07" || activeScreen === "S08") && (
        <span className="ol-ls-lens">{activeScreen === "S07" ? "Trace lens" : "Impact lens"}</span>
      )}
    </div>
  );
}
