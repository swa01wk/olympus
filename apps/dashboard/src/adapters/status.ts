/**
 * Maps backend status strings to UI presentation keys.
 * Display only — never send UI keys to the API.
 */

export type Tone =
  | "neutral"
  | "active"
  | "success"
  | "attention"
  | "failure"
  | "future"
  | "muted";

export type StatusPresentation = {
  uiKey: string;
  label: string;
  tone: Tone;
  glyph: string;
};

/** Design vocabulary (reference-implementation/model.ts STATUS). */
export const STATUS: Record<string, Omit<StatusPresentation, "uiKey">> = {
  recorded: { label: "Recorded", tone: "success", glyph: "■" },
  observed: { label: "Observed fact", tone: "success", glyph: "■" },
  proposed: { label: "Proposed", tone: "neutral", glyph: "◇" },
  review: { label: "Review required", tone: "attention", glyph: "‖" },
  approved: { label: "Approved", tone: "success", glyph: "✓" },
  decided: { label: "Decided", tone: "success", glyph: "✓" },
  ready: { label: "Ready", tone: "active", glyph: "○" },
  blocked: { label: "Blocked", tone: "attention", glyph: "⊘" },
  queued: { label: "Queued", tone: "neutral", glyph: "…" },
  running: { label: "Running", tone: "active", glyph: "●" },
  checkpointed: { label: "Checkpointed", tone: "attention", glyph: "‖" },
  completed: { label: "Completed", tone: "success", glyph: "■" },
  failed: { label: "Failed", tone: "failure", glyph: "✕" },
  stale: { label: "Stale", tone: "attention", glyph: "↻" },
  superseded: { label: "Superseded", tone: "muted", glyph: "—" },
  integrating: { label: "Integrating", tone: "active", glyph: "●" },
  canonical: { label: "Canonical", tone: "success", glyph: "■" },
  provisional: { label: "Provisional", tone: "neutral", glyph: "◇" },
  missing: { label: "Missing", tone: "attention", glyph: "!" },
  passed: { label: "Passed", tone: "success", glyph: "✓" },
  pending: { label: "Pending", tone: "attention", glyph: "‖" },
  rejected: { label: "Rejected", tone: "failure", glyph: "✕" },
  eligible: { label: "Eligible", tone: "success", glyph: "✓" },
  "not-eligible": { label: "Not eligible", tone: "neutral", glyph: "○" },
  "approval-pending": { label: "Awaiting approval", tone: "attention", glyph: "‖" },
  released: { label: "Released", tone: "success", glyph: "■" },
  reproduced: { label: "Failure reproduced", tone: "failure", glyph: "✕" },
  inferred: { label: "Proposed inference", tone: "attention", glyph: "◐" },
  future: { label: "Future obligation", tone: "future", glyph: "○" },
  denied: { label: "Denied", tone: "failure", glyph: "⊘" },
  historical: { label: "Historical", tone: "muted", glyph: "—" },
  promoted: { label: "Promoted", tone: "success", glyph: "✓" },
  resolved: { label: "Resolved", tone: "success", glyph: "✓" },
  "not-ready": { label: "Not ready", tone: "attention", glyph: "○" },
};

/** Backend enum value → UI key */
const BACKEND_TO_UI: Record<string, string> = {
  // TaskStatus
  DRAFT: "proposed",
  BLOCKED: "blocked",
  READY: "ready",
  QUEUED: "queued",
  RUNNING: "running",
  COMPLETED: "completed",
  FAILED: "failed",
  CANCELLED: "rejected",
  STALE: "stale",
  REVALIDATION_REQUIRED: "review",
  // ExecutionStatus
  LEASED: "running",
  STARTED: "running",
  CHECKPOINTED: "checkpointed",
  OUTPUT_PRODUCED: "running",
  VALIDATING: "running",
  COMMITTED: "running",
  TIMED_OUT: "failed",
  // SpecStatus
  PROPOSED: "proposed",
  APPROVED: "approved",
  SUPERSEDED: "superseded",
  REJECTED: "rejected",
  PROMOTED: "promoted",
  CONFIRMED_EXISTING: "observed",
  // ICStatus
  CREATED: "proposed",
  INTEGRATING: "integrating",
  CONFLICT: "failed",
  // GateStatus
  PASS: "passed",
  FAIL: "failed",
  PENDING: "pending",
  // ApprovalStatus
  CHANGES_REQUESTED: "review",
  EXPIRED: "stale",
  // ReleaseStatus (common)
  EXECUTED: "released",
  // ActionStatus
  REQUESTED: "pending",
  DENIED: "denied",
  PENDING_APPROVAL: "approval-pending",
  EXECUTING: "running",
  SUCCEEDED: "passed",
  RECONCILIATION_REQUIRED: "review",
  // ConnectorActionStatus
  FAILED_RETRYABLE: "review",
  FAILED_FINAL: "failed",
  UNKNOWN: "review",
  // FindingStatus
  OPEN: "review",
  IN_REMEDIATION: "running",
  RESOLVED: "resolved",
  WAIVED: "decided",
  // ObligationStatus / evidence
  SATISFIED: "passed",
  UNSATISFIED: "missing",
  NOT_READY: "not-ready",
};

export const ATTENTION_ORDER = [
  "checkpointed",
  "decision",
  "missing",
  "review",
  "pending",
  "approval-pending",
  "inferred",
  "failed",
  "blocked",
] as const;

export function presentationForUiKey(uiKey: string): StatusPresentation {
  const base = STATUS[uiKey];
  if (base) return { uiKey, ...base };
  return {
    uiKey,
    label: uiKey.replace(/-/g, " "),
    tone: "neutral",
    glyph: "·",
  };
}

export function mapBackendStatus(backendValue: string): StatusPresentation {
  const uiKey = BACKEND_TO_UI[backendValue] ?? backendValue.toLowerCase().replace(/_/g, "-");
  return presentationForUiKey(uiKey);
}

export function attentionPriority(uiKey: string): number {
  const idx = ATTENTION_ORDER.indexOf(uiKey as (typeof ATTENTION_ORDER)[number]);
  return idx >= 0 ? idx : ATTENTION_ORDER.length + 1;
}
