export type ChangeRequestSummary = {
  id: string;
  key: string;
  status: string;
  delivery_cycle_id: string | null;
  title: string;
};

export type ChangeInterpretation = {
  interpretation: unknown;
  candidates: unknown[];
  status: string;
};

export type CycleSpecDelta = {
  id: string;
  status: string;
  content_hash: string;
  changes: unknown;
};

export type DefectSummary = {
  id: string;
  key: string;
  status: string;
  delivery_cycle_id: string | null;
  title: string;
  severity: string;
};

export type DefectDetail = {
  id: string;
  key: string;
  status: string;
  title: string;
  description: string;
  triage: unknown;
  linked_feature_ids: string[];
  expected_ac_ids: string[];
  affected_sha: string | null;
  delivery_cycle_id: string | null;
};

export type BrownfieldDiscovery = {
  id: string;
  repository_id: string;
  delivery_cycle_id: string;
  commit_sha: string;
  content: Record<string, unknown>;
  content_hash: string;
};

export type ObservedBehavior = {
  id: string;
  key: string;
  kind: string;
  description: string;
  commit_sha: string;
  confidence: number;
  passed: boolean | null;
};

export type ReviewQueueItem = {
  subject_type: string;
  subject_id: string;
  detail: Record<string, unknown>;
  decided: boolean;
  decision: string | null;
};

export type ReadinessAssessment = {
  id: string;
  delivery_cycle_id: string;
  commit_sha: string;
  metrics: Record<string, unknown>[];
  result: string;
  remediable: boolean;
  reasons: string[];
};
