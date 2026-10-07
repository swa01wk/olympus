/** Six-lane control-plane vocabulary (design 02-navigation, 05-graph-grammar). */

export type LaneId = "intent" | "work" | "exec" | "code" | "evidence" | "outcome";

export type ScreenId =
  | "S01"
  | "S02"
  | "S03"
  | "S04"
  | "S05"
  | "S06"
  | "S07"
  | "S08"
  | "S09"
  | "S10"
  | "INT"
  | "AUD";

export type LensId = "lifecycle" | "trace" | "impact" | "blockers";

export const SCREENS: {
  id: ScreenId;
  num: string;
  name: string;
  mono: string;
  short: string;
  lane?: LaneId;
  lens?: LensId;
}[] = [
  { id: "S01", num: "01", name: "Project Overview", mono: "PO", short: "Project" },
  { id: "S02", num: "02", name: "Delivery Cycle", mono: "MAP", short: "Cycle map" },
  { id: "S03", num: "03", name: "Product / Specs", mono: "IN", short: "Specs", lane: "intent" },
  { id: "S04", num: "04", name: "Task DAG", mono: "WK", short: "Tasks", lane: "work" },
  { id: "S05", num: "05", name: "Execution Inspector", mono: "EX", short: "Runs", lane: "exec" },
  { id: "S06", num: "06", name: "Code Intelligence", mono: "CD", short: "Code", lane: "code" },
  { id: "S07", num: "07", name: "Traceability", mono: "TR", short: "Trace", lens: "trace" },
  { id: "S08", num: "08", name: "Impact Explorer", mono: "IM", short: "Impact", lens: "impact" },
  { id: "S09", num: "09", name: "Assurance", mono: "EV", short: "Assure", lane: "evidence" },
  { id: "S10", num: "10", name: "Release", mono: "OU", short: "Outcome", lane: "outcome" },
];

export const LANES: {
  id: LaneId;
  code: string;
  name: string;
  short: string;
  screen: ScreenId;
  question: string;
}[] = [
  {
    id: "intent",
    code: "IN",
    name: "Intent & product",
    short: "Intent",
    screen: "S03",
    question: "What is wanted, and which version is approved?",
  },
  {
    id: "work",
    code: "WK",
    name: "Planned work",
    short: "Work",
    screen: "S04",
    question: "What durable work exists, and why is it ready or blocked?",
  },
  {
    id: "exec",
    code: "EX",
    name: "Executions",
    short: "Execution",
    screen: "S05",
    question: "Which bounded attempts ran, and what did they produce?",
  },
  {
    id: "code",
    code: "CD",
    name: "Canonical code",
    short: "Code",
    screen: "S06",
    question: "What does the repository structurally contain, at which SHA?",
  },
  {
    id: "evidence",
    code: "EV",
    name: "Evidence & decisions",
    short: "Evidence",
    screen: "S09",
    question: "What proves it, and who decided?",
  },
  {
    id: "outcome",
    code: "OU",
    name: "Outcome",
    short: "Outcome",
    screen: "S10",
    question: "What was delivered, and is it eligible?",
  },
];

export const LANE_BY_CODE = Object.fromEntries(LANES.map((l) => [l.code, l])) as Record<
  string,
  (typeof LANES)[number]
>;

export const LANE_BY_ID = Object.fromEntries(LANES.map((l) => [l.id, l])) as Record<
  LaneId,
  (typeof LANES)[number]
>;

export function laneIndex(id: LaneId): number {
  return LANES.findIndex((l) => l.id === id);
}

/** Record kinds mapped to lanes for graph adapter (Phase 3). */
export const RECORD_KIND_LANE: Record<string, LaneId> = {
  ProductSource: "intent",
  Capability: "intent",
  Feature: "intent",
  FeatureSpec: "intent",
  SpecDelta: "intent",
  AcceptanceCriterion: "intent",
  ImplementationSpec: "intent",
  Architecture: "intent",
  ChangeRequest: "intent",
  Defect: "intent",
  Clarification: "intent",
  Decomposition: "intent",
  ChangeInterpretation: "intent",
  ObservedBehavior: "intent",
  RecoveredSpec: "intent",
  KnowledgeItem: "intent",
  Task: "work",
  TaskDependency: "work",
  TaskPlan: "work",
  TaskContract: "work",
  Execution: "exec",
  ExecutionSnapshot: "exec",
  ActionRequest: "exec",
  Artifact: "exec",
  ModelCall: "exec",
  Repository: "code",
  CodeIndexVersion: "code",
  IntegrationCandidate: "code",
  CandidateCommit: "code",
  CodeEntity: "code",
  Evidence: "evidence",
  VerificationObligation: "evidence",
  Gate: "evidence",
  Finding: "evidence",
  Approval: "evidence",
  Baseline: "evidence",
  PromotionDecision: "evidence",
  ReadinessAssessment: "evidence",
  Review: "evidence",
  Release: "outcome",
  ReleaseManifest: "outcome",
  ReleaseEligibilityEvaluation: "outcome",
  DeliveryOutcome: "outcome",
};

export function laneForRecordKind(kind: string): LaneId | undefined {
  return RECORD_KIND_LANE[kind];
}
