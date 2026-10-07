import {
  STAGES_BY_CYCLE_TYPE,
  type DeliveryCycleType,
} from "@/src/control-plane/stage-lanes";

/** Stages that reuse Greenfield C4 workspace views across journey types. */
export const SHARED_EXECUTION_STAGES = new Set([
  "PLANNING",
  "DEVELOPMENT",
  "INTEGRATION",
  "ASSURANCE",
  "RELEASE",
  "COMPLETE",
]);

export function isKnownStudioStage(cycleType: DeliveryCycleType, stage: string): boolean {
  const ordered = STAGES_BY_CYCLE_TYPE[cycleType];
  return ordered ? ordered.includes(stage) : false;
}

export function usesSharedExecutionView(cycleType: DeliveryCycleType, stage: string): boolean {
  if (cycleType === "GREENFIELD_BUILD") {
    return STAGES_BY_CYCLE_TYPE.GREENFIELD_BUILD.includes(stage);
  }
  return SHARED_EXECUTION_STAGES.has(stage);
}
