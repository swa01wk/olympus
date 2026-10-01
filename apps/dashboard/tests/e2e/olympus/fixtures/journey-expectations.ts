import { SHAS } from "@/lib/fixtures/supportdesk/shas";
import { formatShortSha } from "@/lib/utils/sha";
import type { ScenarioId } from "@/lib/api/scenario-controller";

export const SHA = {
  gfInit: { label: "gf-init-001", full: SHAS.gfInit, short: formatShortSha(SHAS.gfInit) },
  r1: { label: "73fb91d", full: SHAS.r1Integrated, short: formatShortSha(SHAS.r1Integrated) },
  r2: { label: "r2-def456", full: SHAS.r2Integrated, short: formatShortSha(SHAS.r2Integrated) },
  ic004: { label: "982af11", full: SHAS.ic004Integrated, short: formatShortSha(SHAS.ic004Integrated) },
  r3: { label: "r3-a41c9e0", full: SHAS.r3Integrated, short: formatShortSha(SHAS.r3Integrated) },
  c551: { label: "aaa5511", full: SHAS.candidate551, short: formatShortSha(SHAS.candidate551) },
} as const;

export const PROJECT_KEY = "SUPPORTDESK";

/** Stable SupportDesk fixture project id (public demo UUID; resolved once in fixture world). */
export const PROJECT_ID = "11111111-1111-4111-8111-111111111101";

export const CYCLE_IDS = {
  dc001: "11111111-1111-4111-8111-111111111201",
  dc002: "11111111-1111-4111-8111-111111111202",
  dc003: "11111111-1111-4111-8111-111111111203",
  dc004: "11111111-1111-4111-8111-111111111204",
} as const;

export const DELIVERY_CYCLES = {
  greenfield: "DC-001",
  brownfield: "DC-002",
  featureChange: "DC-003",
  bugFix: "DC-004",
} as const;

/** Facts asserted in vitest (world) and Playwright (UI) at selected checkpoints. */
export type CheckpointExpectation = {
  cycleKey?: string;
  cycleState?: string;
  canonicalSha?: string;
  integratedIc?: string;
  releaseKey?: string;
  releaseStatus?: string;
  tasks?: Array<{ key: string; status: string }>;
  executions?: string[];
  defectKey?: string;
  readiness?: string;
};

export const CHECKPOINT_EXPECTATIONS: Partial<
  Record<ScenarioId, Record<string, CheckpointExpectation>>
> = {
  "feature-change": {
    "05-development-running": {
      cycleKey: "DC-003",
      cycleState: "DEVELOPMENT",
      canonicalSha: SHAS.r1Integrated,
      executions: ["EX-548", "EX-551", "EX-552"],
      tasks: [
        { key: "TASK-221", status: "RUNNING" },
        { key: "TASK-223", status: "BLOCKED" },
      ],
    },
    "08-canonical-reindex": {
      cycleKey: "DC-003",
      canonicalSha: SHAS.r2Integrated,
      integratedIc: "IC-003",
    },
    "11-released": {
      releaseKey: "R2",
      releaseStatus: "RELEASED",
      canonicalSha: SHAS.r2Integrated,
      integratedIc: "IC-003",
    },
  },
  "bug-fix": {
    "07-assurance-fail": {
      cycleKey: "DC-004",
      defectKey: "DEF-004",
      releaseKey: "R3",
      releaseStatus: "NOT_ELIGIBLE",
    },
    "11-released": {
      releaseKey: "R3",
      releaseStatus: "RELEASED",
      canonicalSha: SHAS.r3Integrated,
      integratedIc: "IC-005",
    },
  },
  brownfield: {
    "11-ready-for-change": {
      cycleKey: "DC-002",
      readiness: "READY_FOR_CHANGE",
    },
  },
  greenfield: {
    "14-released": {
      cycleKey: "DC-001",
      releaseKey: "R1",
      releaseStatus: "RELEASED",
      canonicalSha: SHAS.r1Integrated,
      integratedIc: "IC-001",
    },
  },
};
