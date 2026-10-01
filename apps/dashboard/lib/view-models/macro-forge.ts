import type { StageDisplayState } from "@/lib/view-models/lifecycle";
import { buildForgeStages, type ForgeStageVM } from "@/lib/view-models/lifecycle";
import type { TransitionPreview } from "@/lib/contracts/entity-types";

export type MacroBandId =
  | "INTAKE"
  | "SPECIFICATION"
  | "IMPACT"
  | "PLANNING"
  | "DEVELOPMENT"
  | "INTEGRATION"
  | "ASSURANCE"
  | "RELEASE"
  | "COMPLETE";

export interface MacroBandVM {
  id: MacroBandId;
  label: string;
  display: StageDisplayState;
  states: string[];
  gateAfter?: "APPROVAL";
}

const STATE_TO_BAND: Record<string, MacroBandId> = {
  DISCOVERY: "INTAKE",
  INTAKE: "INTAKE",
  TRIAGE: "INTAKE",
  RECON: "INTAKE",
  PRODUCT_MODEL: "SPECIFICATION",
  SPEC_DELTA: "SPECIFICATION",
  ARCHITECTURE: "SPECIFICATION",
  IMPACT_ANALYSIS: "IMPACT",
  PLANNING: "PLANNING",
  DEVELOPMENT: "DEVELOPMENT",
  CODE_INDEX: "DEVELOPMENT",
  RECOVERED_SPEC: "SPECIFICATION",
  BASELINE: "ASSURANCE",
  READINESS: "ASSURANCE",
  REMEDIATION: "DEVELOPMENT",
  INTEGRATION: "INTEGRATION",
  REPRODUCTION: "ASSURANCE",
  EXPECTED_BEHAVIOR: "SPECIFICATION",
  ROOT_CAUSE: "SPECIFICATION",
  REGRESSION: "ASSURANCE",
  ASSURANCE: "ASSURANCE",
  RELEASE: "RELEASE",
  COMPLETE: "COMPLETE",
  READY: "COMPLETE",
};

const BAND_ORDER: MacroBandId[] = [
  "INTAKE",
  "SPECIFICATION",
  "IMPACT",
  "PLANNING",
  "DEVELOPMENT",
  "INTEGRATION",
  "ASSURANCE",
  "RELEASE",
  "COMPLETE",
];

const BAND_LABEL: Record<MacroBandId, string> = {
  INTAKE: "Intake",
  SPECIFICATION: "Specification",
  IMPACT: "Impact",
  PLANNING: "Planning",
  DEVELOPMENT: "Development",
  INTEGRATION: "Integration",
  ASSURANCE: "Assurance",
  RELEASE: "Release",
  COMPLETE: "Complete",
};

function bandDisplay(stages: ForgeStageVM[], bandId: MacroBandId): StageDisplayState {
  const inBand = stages.filter((s) => STATE_TO_BAND[s.state] === bandId);
  if (inBand.length === 0) return "NOT_STARTED";
  const ranks: StageDisplayState[] = [
    "FAILED",
    "BLOCKED",
    "ACTIVE",
    "WAITING",
    "READY",
    "COMPLETE",
    "NOT_STARTED",
  ];
  for (const r of ranks) {
    if (inBand.some((s) => s.display === r)) return r;
  }
  return "NOT_STARTED";
}

/** Presentation macro-bands over journey states (APPROVAL shown as gate markers). */
export function buildMacroBands(
  cycleType: string,
  currentState: string,
  previews: TransitionPreview[],
  opts?: { runningExecutions?: number },
): MacroBandVM[] {
  const stages = buildForgeStages(cycleType, currentState, previews, opts);
  const present = new Set(stages.map((s) => STATE_TO_BAND[s.state]).filter(Boolean));

  return BAND_ORDER.filter((id) => present.has(id)).map((id) => ({
    id,
    label: BAND_LABEL[id],
    display: bandDisplay(stages, id),
    states: stages.filter((s) => STATE_TO_BAND[s.state] === id).map((s) => s.state),
    gateAfter: id === "SPECIFICATION" || id === "PLANNING" ? "APPROVAL" : undefined,
  }));
}
