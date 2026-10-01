"use client";

import type { ForgeStageVM, StageDisplayState } from "@/lib/view-models/lifecycle";
import { cn } from "@/lib/utils";

const displayRing: Record<StageDisplayState, string> = {
  COMPLETE: "border-emerald-500/50 bg-emerald-500/5",
  ACTIVE: "border-amber-400 ring-2 ring-amber-400/30",
  WAITING: "border-violet-500/40 bg-violet-500/5",
  BLOCKED: "border-orange-500/50 bg-orange-500/5",
  FAILED: "border-rose-500/50 bg-rose-500/5",
  READY: "border-slate-500/50 border-dashed",
  NOT_STARTED: "border-slate-700 border-dashed opacity-60",
};

export function LifecycleForge({
  stages,
  variant = "full",
  onSelectStage,
  selectedState,
}: {
  stages: ForgeStageVM[];
  variant?: "full" | "compact";
  onSelectStage?: (state: string) => void;
  selectedState?: string;
}) {
  return (
    <div
      className={cn(
        "flex gap-2 overflow-x-auto pb-2",
        variant === "compact" && "scale-95 origin-left",
      )}
      role="list"
      aria-label="Delivery lifecycle forge"
    >
      {stages.map((stage) => (
        <button
          key={stage.state}
          type="button"
          role="listitem"
          data-testid={`lifecycle-stage-${stage.state}`}
          data-stage-state={stage.display}
          aria-current={stage.display === "ACTIVE" ? "step" : undefined}
          onClick={() => onSelectStage?.(stage.state)}
          className={cn(
            "min-w-[9rem] shrink-0 rounded-lg border px-3 py-2 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500",
            displayRing[stage.display],
            selectedState === stage.state && "ring-2 ring-sky-400",
          )}
        >
          <div className="text-[10px] uppercase tracking-wide text-[var(--muted)]">{stage.state}</div>
          <div className="text-sm font-medium">{stage.label}</div>
          <div className="mt-1 text-xs text-[var(--muted)]">{stage.display.replace("_", " ")}</div>
        </button>
      ))}
    </div>
  );
}
