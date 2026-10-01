export type EventCategory = "lifecycle" | "execution" | "action" | "integration" | "assurance" | "release" | "product" | "audit";

export const EVENT_REGISTRY: Record<string, { category: EventCategory; severity: "info" | "notice" | "warning" | "critical" }> = {
  "execution.started": { category: "execution", severity: "info" },
  "execution.completed": { category: "execution", severity: "info" },
  "execution.failed": { category: "execution", severity: "critical" },
  "action.requested": { category: "action", severity: "notice" },
  "action.completed": { category: "action", severity: "info" },
  "action.denied": { category: "action", severity: "warning" },
  "task.ready": { category: "lifecycle", severity: "info" },
  "task.blocked": { category: "lifecycle", severity: "warning" },
  "candidate_commit.created": { category: "integration", severity: "info" },
  "integration.ready": { category: "integration", severity: "info" },
  "gate.finalized": { category: "assurance", severity: "notice" },
  "approval.decided": { category: "assurance", severity: "notice" },
  "approval.requested": { category: "assurance", severity: "notice" },
  "release.eligible": { category: "release", severity: "info" },
  "release.blocked": { category: "release", severity: "warning" },
  "delivery_cycle.transitioned": { category: "lifecycle", severity: "info" },
  "code_index.updated": { category: "product", severity: "info" },
};
