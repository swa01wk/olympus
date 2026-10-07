import type { LaneId } from "./lanes";
import { LANE_BY_CODE } from "./lanes";

/** Backend DeliveryCycleType values from core/domain/enums.py */
export type DeliveryCycleType =
  | "GREENFIELD_BUILD"
  | "BROWNFIELD_ONBOARDING"
  | "FEATURE_CHANGE"
  | "BUG_FIX"
  | "REMEDIATION";

export type StageLane = {
  state: string;
  laneCode: string;
  laneId: LaneId;
};

function stages(entries: [string, string][]): StageLane[] {
  return entries.map(([state, laneCode]) => ({
    state,
    laneCode,
    laneId: LANE_BY_CODE[laneCode].id,
  }));
}

/** Ordered machine states per cycle type (§1). Same order as `STAGE_LANES_BY_TYPE`. */
export const STAGES_BY_CYCLE_TYPE: Record<DeliveryCycleType, readonly string[]> = {
  GREENFIELD_BUILD: [
    "DISCOVERY",
    "PRODUCT_MODEL",
    "ARCHITECTURE",
    "PLANNING",
    "DEVELOPMENT",
    "INTEGRATION",
    "ASSURANCE",
    "RELEASE",
    "COMPLETE",
  ],
  BROWNFIELD_ONBOARDING: [
    "RECON",
    "CODE_INDEX",
    "RECOVERED_SPEC",
    "BASELINE",
    "READINESS",
    "REMEDIATION",
    "READY",
  ],
  FEATURE_CHANGE: [
    "INTAKE",
    "SPEC_DELTA",
    "IMPACT_ANALYSIS",
    "PLANNING",
    "DEVELOPMENT",
    "INTEGRATION",
    "ASSURANCE",
    "RELEASE",
    "COMPLETE",
  ],
  BUG_FIX: [
    "TRIAGE",
    "REPRODUCTION",
    "EXPECTED_BEHAVIOR",
    "ROOT_CAUSE",
    "DEVELOPMENT",
    "INTEGRATION",
    "REGRESSION",
    "ASSURANCE",
    "RELEASE",
    "COMPLETE",
  ],
  REMEDIATION: [
    "INTAKE",
    "PLANNING",
    "DEVELOPMENT",
    "INTEGRATION",
    "ASSURANCE",
    "RELEASE",
    "COMPLETE",
  ],
};

export const STAGE_LANES_BY_TYPE: Record<DeliveryCycleType, StageLane[]> = {
  GREENFIELD_BUILD: stages([
    ["DISCOVERY", "IN"],
    ["PRODUCT_MODEL", "IN"],
    ["ARCHITECTURE", "IN"],
    ["PLANNING", "WK"],
    ["DEVELOPMENT", "EX"],
    ["INTEGRATION", "CD"],
    ["ASSURANCE", "EV"],
    ["RELEASE", "OU"],
    ["COMPLETE", "OU"],
  ]),
  BROWNFIELD_ONBOARDING: stages([
    ["RECON", "CD"],
    ["CODE_INDEX", "CD"],
    ["RECOVERED_SPEC", "IN"],
    ["BASELINE", "EV"],
    ["READINESS", "EV"],
    ["REMEDIATION", "WK"],
    ["READY", "OU"],
  ]),
  FEATURE_CHANGE: stages([
    ["INTAKE", "IN"],
    ["SPEC_DELTA", "IN"],
    ["IMPACT_ANALYSIS", "CD"],
    ["PLANNING", "WK"],
    ["DEVELOPMENT", "EX"],
    ["INTEGRATION", "CD"],
    ["ASSURANCE", "EV"],
    ["RELEASE", "OU"],
    ["COMPLETE", "OU"],
  ]),
  BUG_FIX: stages([
    ["TRIAGE", "IN"],
    ["REPRODUCTION", "EV"],
    ["EXPECTED_BEHAVIOR", "IN"],
    ["ROOT_CAUSE", "CD"],
    ["DEVELOPMENT", "EX"],
    ["INTEGRATION", "CD"],
    ["REGRESSION", "EV"],
    ["ASSURANCE", "EV"],
    ["RELEASE", "OU"],
    ["COMPLETE", "OU"],
  ]),
  REMEDIATION: stages([
    ["INTAKE", "IN"],
    ["PLANNING", "WK"],
    ["DEVELOPMENT", "EX"],
    ["INTEGRATION", "CD"],
    ["ASSURANCE", "EV"],
    ["RELEASE", "OU"],
    ["COMPLETE", "OU"],
  ]),
};

export const TERMINAL_CYCLE_STATES = new Set(["COMPLETE", "READY", "CANCELLED", "FAILED"]);

export function stagesForCycleType(type: DeliveryCycleType): StageLane[] {
  return STAGE_LANES_BY_TYPE[type] ?? [];
}

export function laneForCycleState(type: DeliveryCycleType, state: string): StageLane | undefined {
  return stagesForCycleType(type).find((s) => s.state === state);
}

export function stageIndex(type: DeliveryCycleType, state: string): number {
  return stagesForCycleType(type).findIndex((s) => s.state === state);
}

/** Ordered lifecycle states for ribbon (excludes terminal unless current). */
export function ribbonStages(type: DeliveryCycleType, currentState: string): StageLane[] {
  const all = stagesForCycleType(type);
  if (TERMINAL_CYCLE_STATES.has(currentState)) {
    const idx = all.findIndex((s) => s.state === currentState);
    if (idx >= 0) return all.slice(0, idx + 1);
    return [...all, { state: currentState, laneCode: "OU", laneId: "outcome" as LaneId }];
  }
  const currentIdx = all.findIndex((s) => s.state === currentState);
  if (currentIdx < 0) return all;
  return all.slice(0, currentIdx + 1);
}
