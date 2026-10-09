/** Types aligned with Control API response models (read-only). */

export type DeliveryCycleType =
  | "GREENFIELD_BUILD"
  | "BROWNFIELD_ONBOARDING"
  | "FEATURE_CHANGE"
  | "BUG_FIX"
  | "REMEDIATION";

export type AllowedCommand = {
  command: string;
  to_state: string;
  guard_preview: string[];
  allowed: boolean;
};

export type DeliveryCycle = {
  id: string;
  project_id: string;
  key: string;
  type: DeliveryCycleType;
  objective: string;
  state: string;
  state_version: number;
  repository_id: string | null;
  base_sha: string | null;
  allowed_commands: AllowedCommand[];
};

export type Project = {
  id: string;
  key: string;
  name: string;
  description: string | null;
  readiness_state: string;
};

export type Task = {
  id: string;
  delivery_cycle_id: string;
  key: string;
  title: string;
  work_type: string;
  origin: string;
  status: string;
  priority: number;
  blocked_reason: string | null;
};

export type Execution = {
  id: string;
  key: string;
  task_id: string;
  status: string;
  attempt_number: number;
  executor_kind: string;
  snapshot_hash: string | null;
  failure_class: string | null;
};

export type IntegrationCandidate = {
  id: string;
  key: string;
  delivery_cycle_id: string;
  repository_id: string;
  base_sha: string;
  integration_branch: string;
  integrated_sha: string | null;
  status: string;
};

export type VerificationObligation = {
  id: string;
  subject_key: string;
  required: boolean;
  reason: string;
  status: string;
};

export type GuardResult = {
  guard_id: string;
  ok: boolean;
  reasons: string[];
};

export type TransitionPreview = {
  command: string;
  to_state: string;
  target_state: string;
  allowed: boolean;
  guard_preview: string[];
  guard_results: GuardResult[];
  authorization_denied: boolean;
};

export type CycleOverviewView = {
  delivery_cycle_id: string;
  key: string;
  state: string;
  running_executions: number;
  blocked_tasks: number;
  pending_approvals: number;
  integration_candidate_key: string | null;
  next_transitions: TransitionPreview[];
};

export type ControlPlaneSummaryView = {
  delivery_cycle_id: string;
  scheduler: { queued_tasks: number; blocked_tasks: number };
  execution_manager: { running: number };
  policy: { denied_actions: number };
  integration: { active_ic: string | null };
  assurance: { sentinel_fail: boolean };
  release: { eligible: boolean | null };
};

export type InboxApprovalNested = {
  id: string;
  key: string;
  approval_type: string;
  subject_type: string;
  subject_id: string;
  subject_hash: string;
  status: string;
};

export type ApprovalView = {
  id: string;
  key: string;
  approval_type: string;
  subject_type: string;
  subject_id: string;
  subject_version: number;
  subject_hash: string;
  status: string;
  project_id: string;
  delivery_cycle_id: string | null;
  created_at: string;
  decided_by_actor_id: string | null;
  decided_at: string | null;
  decision_note: string | null;
};

export type InboxClarificationNested = {
  id: string;
  key: string;
  question: string;
  status: string;
};

export type InboxItem = {
  kind: string;
  id: string;
  title: string;
  why?: string;
  project_id?: string;
  delivery_cycle_id?: string | null;
  approval?: InboxApprovalNested;
  clarification?: InboxClarificationNested;
};

export type DomainEventPayload = {
  id: string;
  sequence: number;
  event_type: string;
  payload: Record<string, unknown>;
};

export type ApiErrorBody = {
  code?: string;
  message?: string;
  details?: unknown;
  detail?: unknown;
};
