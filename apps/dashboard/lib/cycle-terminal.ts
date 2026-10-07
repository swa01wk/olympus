import { TERMINAL_CYCLE_STATES } from "@/src/control-plane/stage-lanes";

export const NEGATIVE_TERMINAL_STATES = new Set(["CANCELLED", "FAILED"]);

export function isTerminalCycleState(state: string): boolean {
  return TERMINAL_CYCLE_STATES.has(state);
}

export function isNegativeTerminal(state: string): boolean {
  return NEGATIVE_TERMINAL_STATES.has(state);
}

export function terminalConsequence(state: string): string | undefined {
  if (state === "CANCELLED") {
    return "Cycle closed without delivery. No further transitions unless a new cycle is opened.";
  }
  if (state === "FAILED") {
    return "Cycle failed; inspect findings and outcome records. Retry requires a new attempt path under policy.";
  }
  if (state === "COMPLETE" || state === "READY") {
    return "Terminal success state — operate via outcome and lineage, not lifecycle commands.";
  }
  return undefined;
}
