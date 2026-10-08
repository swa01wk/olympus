import { REQUEST_CHANGES_INTERIM_HELPER } from "@/lib/changes-requested-audit";

/** Approval types with no producing agent (RL2.3 table). */
const NO_REVISION_AGENT_TYPES = new Set([
  "RELEASE",
  "FINDING_WAIVER",
  "ACTION",
  "PROMOTION",
  "UNREPRODUCED_REPAIR",
]);

export const REQUEST_CHANGES_AGENT_HELPER = "The agent will revise using your note.";

export function requestChangesHelperText(approvalType: string): string {
  if (NO_REVISION_AGENT_TYPES.has(approvalType)) {
    return REQUEST_CHANGES_INTERIM_HELPER;
  }
  return REQUEST_CHANGES_AGENT_HELPER;
}
