import type { TransitionPreview } from "@/lib/contracts/entity-types";
import { journeyStates } from "@/lib/journeys/definitions";

export type StageDisplayState =
  | "NOT_STARTED"
  | "READY"
  | "ACTIVE"
  | "WAITING"
  | "BLOCKED"
  | "FAILED"
  | "COMPLETE";

export interface ForgeStageVM {
  state: string;
  label: string;
  display: StageDisplayState;
  owningCapabilities: string[];
  forwardCommand?: string;
  transitionPreview?: TransitionPreview;
}

export function buildForgeStages(
  cycleType: string,
  currentState: string,
  previews: TransitionPreview[],
  opts?: { runningExecutions?: number; terminalFailed?: boolean },
): ForgeStageVM[] {
  const defs = journeyStates(cycleType);
  const idx = defs.findIndex((d) => d.state === currentState);
  const previewByCmd = new Map(previews.map((p) => [p.command, p]));

  return defs.map((def, i) => {
    let display: StageDisplayState = "NOT_STARTED";
    if (currentState === "FAILED" || currentState === "CANCELLED") {
      display = i === idx ? "FAILED" : i < idx ? "COMPLETE" : "NOT_STARTED";
    } else if (i < idx) display = "COMPLETE";
    else if (i === idx) {
      if (opts?.terminalFailed) display = "FAILED";
      else if ((opts?.runningExecutions ?? 0) > 0) display = "ACTIVE";
      else display = "READY";
    } else if (i === idx + 1) {
      const fwd = def.forwardCommand;
      const p = fwd ? previewByCmd.get(fwd) : undefined;
      display = p?.allowed ? "READY" : "NOT_STARTED";
    }
    const preview = def.forwardCommand
      ? previewByCmd.get(def.forwardCommand)
      : undefined;
    return {
      state: def.state,
      label: def.label,
      display,
      owningCapabilities: def.capabilities,
      forwardCommand: def.forwardCommand,
      transitionPreview: preview,
    };
  });
}
