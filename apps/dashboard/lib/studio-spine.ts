import type { InboxApprovalNested, InboxItem, TransitionPreview } from "@/src/api/types/core";
import type { DeliveryCycleType } from "@/src/control-plane/stage-lanes";
import { STAGES_BY_CYCLE_TYPE } from "@/src/control-plane/stage-lanes";

export type SpineStageStatus = "done" | "current" | "waiting" | "blocked" | "future";

/** Maps pending approval types to lifecycle stage (Decision panel / §5). */
export const APPROVAL_TYPE_TO_STAGE: Record<string, string> = {
  SCOPE: "PRODUCT_MODEL",
  ARCHITECTURE: "ARCHITECTURE",
  ARCHITECTURE_DELTA: "ARCHITECTURE",
  IMPLEMENTATION_SPEC: "PLANNING",
  SPEC_DELTA: "SPEC_DELTA",
  SPEC_DECISION: "SPEC_DELTA",
  REPAIR_SPEC: "ROOT_CAUSE",
  UNREPRODUCED_REPAIR: "REPRODUCTION",
  EXPECTED_BEHAVIOR: "EXPECTED_BEHAVIOR",
  PROMOTION: "BASELINE",
  READINESS: "READINESS",
  FINDING_WAIVER: "ASSURANCE",
  ACTION: "DEVELOPMENT",
  RELEASE: "RELEASE",
  DEPLOYMENT: "RELEASE",
};

export function formatStageLabel(state: string): string {
  return state.replace(/_/g, " ");
}

export function stagesForType(type: DeliveryCycleType): readonly string[] {
  return STAGES_BY_CYCLE_TYPE[type] ?? [];
}

export function findPendingApprovalForStage(
  inbox: InboxItem[],
  stage: string,
): InboxApprovalNested | null {
  for (const item of inbox) {
    const a = item.approval;
    if (a?.status === "PENDING" && APPROVAL_TYPE_TO_STAGE[a.approval_type] === stage) {
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

export function inboxStagesForCycle(inbox: InboxItem[]): Set<string> {
  const stages = new Set<string>();
  for (const item of inbox) {
    if (item.kind === "APPROVAL" && item.approval?.approval_type) {
      const stage = APPROVAL_TYPE_TO_STAGE[item.approval.approval_type];
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
