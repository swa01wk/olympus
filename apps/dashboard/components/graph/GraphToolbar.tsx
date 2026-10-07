"use client";

import type { LensId } from "@/src/control-plane/lanes";
import { cn } from "@/lib/utils";

const LENSES: { k: LensId; label: string; hint: string }[] = [
  { k: "lifecycle", label: "Lifecycle", hint: "Current stage and selected neighbourhood" },
  { k: "trace", label: "Trace", hint: "Lineage neighbourhood of the selected record" },
  { k: "impact", label: "Impact", hint: "Impact-tagged records" },
  { k: "blockers", label: "Blockers", hint: "Blocked, failed, and missing evidence" },
];

export function GraphToolbar({
  lens,
  onLens,
  view,
  onView,
}: {
  lens: LensId;
  onLens: (l: LensId) => void;
  view: "graph" | "list";
  onView: (v: "graph" | "list") => void;
}) {
  return (
    <div className="ol-gtool">
      <div className="ol-seg" role="radiogroup" aria-label="Lens">
        {LENSES.map((l) => (
          <button
            key={l.k}
            type="button"
            role="radio"
            aria-checked={lens === l.k}
            className={cn("ol-seg-i", lens === l.k && "is-on")}
            onClick={() => onLens(l.k)}
            title={l.hint}
          >
            {l.label}
          </button>
        ))}
      </div>
      <div className="ol-legend" aria-label="Legend">
        <span>
          <svg width="22" height="8" aria-hidden="true">
            <line x1="0" y1="4" x2="22" y2="4" className="ol-lg-auth" />
          </svg>
          authoritative
        </span>
        <span>
          <svg width="22" height="8" aria-hidden="true">
            <line x1="0" y1="4" x2="22" y2="4" className="ol-lg-inf" />
          </svg>
          inferred
        </span>
        <span>
          <svg width="22" height="8" aria-hidden="true">
            <line x1="0" y1="4" x2="22" y2="4" className="ol-lg-obl" />
          </svg>
          obligation
        </span>
      </div>
      <div className="ol-seg" role="radiogroup" aria-label="View">
        {(["graph", "list"] as const).map((v) => (
          <button
            key={v}
            type="button"
            role="radio"
            aria-checked={view === v}
            className={cn("ol-seg-i", view === v && "is-on")}
            onClick={() => onView(v)}
          >
            {v === "graph" ? "Graph" : "List"}
          </button>
        ))}
      </div>
    </div>
  );
}
