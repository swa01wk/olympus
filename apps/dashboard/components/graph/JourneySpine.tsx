"use client";

import { laneIndex, type LaneId } from "@/src/control-plane/lanes";
import { cn } from "@/lib/utils";

export type SpineStage = { state: string; laneId: LaneId };

function spinePoints(stages: SpineStage[], centers: number[], y: number) {
  const perLane: Record<string, number[]> = {};
  stages.forEach((s, i) => {
    perLane[s.laneId] = [...(perLane[s.laneId] ?? []), i];
  });
  return stages.map((s, i) => {
    const arr = perLane[s.laneId];
    const k = arr.indexOf(i);
    const m = arr.length;
    const li = laneIndex(s.laneId);
    const laneW = centers.length > 1 ? Math.abs(centers[1] - centers[0]) : 120;
    const step = Math.min(24, (laneW * 0.92) / Math.max(1, m));
    return {
      i,
      x: centers[li] + (k - (m - 1) / 2) * step,
      y,
      state: s.state,
      r: Math.min(9.5, step / 2.3),
    };
  });
}

export function JourneySpine({
  stages,
  stageIndex,
  centers,
  width,
  height = 52,
}: {
  stages: SpineStage[];
  stageIndex: number;
  centers: number[];
  width: number;
  height?: number;
}) {
  const y = height / 2;
  const pts = spinePoints(stages, centers, y);
  const arcs = pts.slice(1).map((p, idx) => {
    const a = pts[idx];
    const dx = p.x - a.x;
    const fwd = dx >= 0;
    const h = Math.min(fwd ? y - 5 : height - y - 5, Math.abs(dx) * 0.18 + 7);
    const cy = fwd ? y - h * 2 : y + h * 2;
    const done = p.i <= stageIndex;
    return (
      <path
        key={p.i}
        d={`M ${a.x} ${a.y} Q ${(a.x + p.x) / 2} ${cy} ${p.x} ${p.y}`}
        className={cn("ol-spine-arc", done ? "is-done" : "is-next", !fwd && "is-back")}
      />
    );
  });

  return (
    <svg
      className="ol-spine"
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`Journey spine: ${stages.map((s) => s.state).join(" → ")}`}
    >
      {arcs}
      {pts.map((p) => {
        const st = p.i < stageIndex ? "done" : p.i === stageIndex ? "now" : "next";
        return (
          <g key={p.i} className={cn("ol-spine-dot", `is-${st}`)}>
            <title>{`${p.i + 1}. ${p.state}`}</title>
            <circle cx={p.x} cy={p.y} r={p.r} />
            {p.r >= 8 && (
              <text x={p.x} y={p.y + 3.6} textAnchor="middle">
                {p.i + 1}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
