/** Plain-language stages per journey, mapped from backend cycle states. */

export type StageStatus = "done" | "current" | "upcoming";

export type ProgressStage = {
  id: string;
  label: string;
  hint: string;
  states: string[];
};

export type StageView = ProgressStage & { status: StageStatus };

const GREENFIELD: ProgressStage[] = [
  {
    id: "features",
    label: "Understand the PRD",
    hint: "Break your PRD into features you approve",
    states: ["DISCOVERY", "PRODUCT_MODEL"],
  },
  { id: "design", label: "Design", hint: "Pick the stack and structure", states: ["ARCHITECTURE"] },
  {
    id: "plan",
    label: "Plan",
    hint: "Detailed plan per feature, then a task list",
    states: ["PLANNING"],
  },
  { id: "build", label: "Build", hint: "Agents write the code, task by task", states: ["DEVELOPMENT"] },
  {
    id: "check",
    label: "Test & review",
    hint: "Merge, run the tests and review the code",
    states: ["INTEGRATION", "ASSURANCE"],
  },
  { id: "release", label: "Release", hint: "You approve; Olympus tags the release", states: ["RELEASE"] },
];

const BROWNFIELD: ProgressStage[] = [
  { id: "copy", label: "Copy", hint: "Clone your repo; your folder is never edited", states: ["RECON"] },
  { id: "read", label: "Read the code", hint: "Index files, functions and routes", states: ["CODE_INDEX"] },
  {
    id: "learn",
    label: "Learn the app",
    hint: "Work out the features and structure",
    states: ["RECOVERED_SPEC"],
  },
  {
    id: "behavior",
    label: "Record behavior",
    hint: "Run your tests; you confirm what was learned",
    states: ["BASELINE"],
  },
  {
    id: "ready",
    label: "Ready for changes",
    hint: "Check nothing important is missing",
    states: ["READINESS", "REMEDIATION"],
  },
];

const JOURNEYS: Record<string, ProgressStage[]> = {
  GREENFIELD_BUILD: GREENFIELD,
  BROWNFIELD_ONBOARDING: BROWNFIELD,
};

export const JOURNEY_NAMES: Record<string, string> = {
  GREENFIELD_BUILD: "New app",
  BROWNFIELD_ONBOARDING: "Existing repo",
  FEATURE_CHANGE: "Feature",
  BUG_FIX: "Bug fix",
  REMEDIATION: "Clean-up",
};

const TERMINAL_DONE = new Set(["COMPLETE", "READY"]);

export function journeyStages(cycleType: string, cycleState: string): StageView[] {
  const stages = JOURNEYS[cycleType] ?? [];
  if (TERMINAL_DONE.has(cycleState)) {
    return stages.map((s) => ({ ...s, status: "done" }));
  }
  const current = stages.findIndex((s) => s.states.includes(cycleState));
  return stages.map((s, i) => ({
    ...s,
    status: current < 0 ? "upcoming" : i < current ? "done" : i === current ? "current" : "upcoming",
  }));
}

export function journeyName(cycleType: string): string {
  return JOURNEY_NAMES[cycleType] ?? cycleType.replace(/_/g, " ").toLowerCase();
}
