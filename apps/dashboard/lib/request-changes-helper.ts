import type { DeliveryCycleType } from "@/src/control-plane/stage-lanes";

/** Approval types `RevisionService._schedule` never revises. */
const NO_REVISION_AGENT_TYPES = new Set([
  "RELEASE",
  "FINDING_WAIVER",
  "ACTION",
  "PROMOTION",
  "UNREPRODUCED_REPAIR",
]);

const SCOPE_REVISION_STATES = new Set(["DISCOVERY", "PRODUCT_MODEL"]);

export const REQUEST_CHANGES_AGENT_HELPER = "The agent will revise using your note.";

export const REQUEST_CHANGES_NO_REVISION_HELPER =
  "Your note is recorded, but no agent revises this item. To change it, edit it (feature specs) or regenerate it.";

export type RequestChangesContext = {
  approvalType: string;
  cycleType: DeliveryCycleType;
  cycleState: string;
  /** Subject `kind` (architecture / implementation spec) when known. */
  subjectKind?: string | null;
};

export function requestChangesRevises({
  approvalType,
  cycleType,
  cycleState,
  subjectKind,
}: RequestChangesContext): boolean {
  if (NO_REVISION_AGENT_TYPES.has(approvalType)) return false;
  switch (approvalType) {
    case "SCOPE":
      return SCOPE_REVISION_STATES.has(cycleState);
    case "ARCHITECTURE":
      return subjectKind !== "DELTA";
    case "ARCHITECTURE_DELTA":
      return subjectKind == null || subjectKind === "DELTA";
    case "IMPLEMENTATION_SPEC":
      if (subjectKind != null) return subjectKind !== "REMEDIATION";
      return cycleType !== "BROWNFIELD_ONBOARDING";
    case "SPEC_DELTA":
      return true;
    default:
      return false;
  }
}

export function requestChangesHelperText(ctx: RequestChangesContext): string {
  return requestChangesRevises(ctx) ? REQUEST_CHANGES_AGENT_HELPER : REQUEST_CHANGES_NO_REVISION_HELPER;
}
