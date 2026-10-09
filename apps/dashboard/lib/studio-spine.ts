import type { InboxApprovalNested, InboxItem, TransitionPreview } from "@/src/api/types/core";
import type { DeliveryCycleType } from "@/src/control-plane/stage-lanes";
import { STAGES_BY_CYCLE_TYPE } from "@/src/control-plane/stage-lanes";

export type SpineStageStatus = "done" | "current" | "waiting" | "blocked" | "future";

// Backend never creates REPAIR_SPEC, READINESS, SPEC_DECISION, or DEPLOYMENT approvals (plan G5).
// EXPECTED_BEHAVIOR and TASK_PLAN are created from RL3.

/** Maps pending approval types to lifecycle stage (Decision panel / §5), per cycle type. */
export function approvalStage(
  approvalType: string,
  cycleType: DeliveryCycleType,
): string | null {
  switch (approvalType) {
    case "SCOPE":
      return "PRODUCT_MODEL";
    case "ARCHITECTURE":
      if (cycleType === "GREENFIELD_BUILD") return "ARCHITECTURE";
      if (cycleType === "BROWNFIELD_ONBOARDING") return "BASELINE";
      return null;
    case "ARCHITECTURE_DELTA":
      return cycleType === "FEATURE_CHANGE" ? "IMPACT_ANALYSIS" : null;
    case "IMPLEMENTATION_SPEC":
      if (cycleType === "BUG_FIX") return "ROOT_CAUSE";
      if (cycleType === "BROWNFIELD_ONBOARDING") return "REMEDIATION";
      if (
        cycleType === "GREENFIELD_BUILD" ||
        cycleType === "FEATURE_CHANGE" ||
        cycleType === "REMEDIATION"
      ) {
        return "PLANNING";
      }
      return null;
    case "SPEC_DELTA":
      return "SPEC_DELTA";
    case "UNREPRODUCED_REPAIR":
      return "REPRODUCTION";
    case "EXPECTED_BEHAVIOR":
      return "EXPECTED_BEHAVIOR";
    case "TASK_PLAN":
      if (cycleType === "BUG_FIX") return "ROOT_CAUSE";
      return "PLANNING";
    case "PROMOTION":
      return "BASELINE";
    case "FINDING_WAIVER":
      return "ASSURANCE";
    case "ACTION":
      return "DEVELOPMENT";
    case "RELEASE":
      return "RELEASE";
    default:
      return null;
  }
}

export function formatStageLabel(state: string): string {
  return state.replace(/_/g, " ");
}

export function stagesForType(type: DeliveryCycleType): readonly string[] {
  return STAGES_BY_CYCLE_TYPE[type] ?? [];
}

/** The stage's newest approval (by created_at), only when that one is CHANGES_REQUESTED. */
export function findChangesRequestedApprovalForStage<
  T extends {
    approval_type: string;
    status: string;
    delivery_cycle_id: string | null;
    created_at: string;
  },
>(approvals: T[], stage: string, cycleType: DeliveryCycleType, cycleId: string): T | null {
  let latest: T | null = null;
  for (const a of approvals) {
    if (a.delivery_cycle_id !== cycleId) continue;
    if (approvalStage(a.approval_type, cycleType) !== stage) continue;
    if (!latest || Date.parse(a.created_at) > Date.parse(latest.created_at)) {
      latest = a;
    }
  }
  return latest?.status === "CHANGES_REQUESTED" ? latest : null;
}

export function findPendingApprovalForStage(
  inbox: InboxItem[],
  stage: string,
  cycleType: DeliveryCycleType,
): InboxApprovalNested | null {
  for (const item of inbox) {
    const a = item.approval;
    if (
      a?.status === "PENDING" &&
      approvalStage(a.approval_type, cycleType) === stage
    ) {
      return a;
    }
  }
  return null;
}

export function guardResultsForApprovalType(
  approvalType: string,
  transitions: TransitionPreview[],
): TransitionPreview["guard_results"] {
  const keyword = approvalType.toLowerCase().replace(/_/g, "");
  const out: TransitionPreview["guard_results"] = [];
  for (const t of transitions) {
    for (const g of t.guard_results) {
      const id = g.guard_id.toLowerCase().replace(/_/g, "");
      if (id.includes(keyword) || keyword.includes(id.slice(0, 6))) {
        out.push(g);
      }
    }
  }
  return out;
}

export function inboxStagesForCycle(
  inbox: InboxItem[],
  cycleType: DeliveryCycleType,
): Set<string> {
  const stages = new Set<string>();
  for (const item of inbox) {
    if (item.kind === "APPROVAL" && item.approval?.approval_type) {
      const stage = approvalStage(item.approval.approval_type, cycleType);
      if (stage) stages.add(stage);
    }
    if (item.kind === "CLARIFICATION") {
      stages.add("PRODUCT_MODEL");
    }
  }
  return stages;
}

export function isCycleStageBlocked(
  cycleState: string,
  stage: string,
  nextTransitions: TransitionPreview[],
): boolean {
  if (stage !== cycleState) return false;
  const forward = nextTransitions.filter((t) => t.to_state !== cycleState);
  if (forward.length === 0) return false;
  return forward.every((t) => !t.allowed);
}

export function spineStatusForStage(
  stage: string,
  cycleState: string,
  orderedStages: readonly string[],
  opts: {
    inboxStages: Set<string>;
    nextTransitions: TransitionPreview[];
  },
): SpineStageStatus {
  const currentIdx = orderedStages.indexOf(cycleState);
  const stageIdx = orderedStages.indexOf(stage);
  if (stageIdx < 0) return "future";

  if (opts.inboxStages.has(stage)) return "waiting";

  if (stageIdx < currentIdx) return "done";
  if (stageIdx > currentIdx) return "future";

  if (isCycleStageBlocked(cycleState, stage, opts.nextTransitions)) return "blocked";
  return "current";
}

export const SPINE_GLYPH: Record<SpineStageStatus, string> = {
  done: "✓",
  current: "●",
  waiting: "‖",
  blocked: "⊘",
  future: "○",
};

export const SPINE_STATUS_WORD: Record<SpineStageStatus, string> = {
  done: "Done",
  current: "Current",
  waiting: "Waiting on you",
  blocked: "Blocked",
  future: "Future",
};
