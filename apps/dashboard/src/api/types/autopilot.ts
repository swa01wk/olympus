export type AutopilotStatus = "OFF" | "WORKING" | "NEEDS_YOU" | "BLOCKED" | "DONE";

export type AutopilotDetail = {
  approval_ids?: string[];
  approval_type?: string;
  clarification_ids?: string[];
  task_ids?: string[];
  retryable?: boolean;
  done?: number;
  total?: number;
  integration_candidate_id?: string;
  retry_tasks?: boolean;
  count?: number;
  reasons?: string[];
  /** Branch in the person's folder that holds the released code. */
  branch?: string;
  folder?: string;
};

export type AutopilotView = {
  delivery_cycle_id: string;
  supported: boolean;
  enabled: boolean;
  status: AutopilotStatus;
  step: string;
  message: string;
  detail: AutopilotDetail;
  last_error: string | null;
  updated_at: string | null;
  /** Where the project's code lives on this machine. */
  code_path: string | null;
};

export type HomeRun = {
  delivery_cycle_id: string;
  type: string;
  state: string;
  objective: string;
  created_at: string;
  autopilot: AutopilotView;
};

export type HomeProject = {
  id: string;
  key: string;
  name: string;
  local_path: string | null;
  latest_run: HomeRun | null;
};

export type StartJourneyInput = {
  name: string;
  prd_title: string;
  prd_text: string;
};

export type StartJourneyResult = {
  project_id: string;
  delivery_cycle_id: string;
  autopilot: AutopilotView;
};

export type ActivityEvent = {
  id: string;
  sequence: number;
  event_type: string;
  payload: { status?: AutopilotStatus; step?: string; message?: string };
  occurred_at: string;
};

export type ReviewItem = {
  subject_type: string;
  subject_id: string;
  group: string;
  title: string;
  detail: string | null;
  suggestion: "keep" | "drop";
  why: string | null;
  keep_label: string;
  drop_label: string;
};

export type ReviewChoice = {
  subject_type: string;
  subject_id: string;
  choice: "keep" | "drop";
};
