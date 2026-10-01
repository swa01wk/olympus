import { z } from "zod";
import { IsoDateTime, Uuid } from "./common";
import { KnowledgeClass } from "./enums";

export const RecoveredSpec = z.object({
  id: Uuid,
  project_id: Uuid,
  delivery_cycle_id: Uuid,
  key: z.string(),
  spec_kind: z.string(),
  title: z.string(),
  knowledge_class: KnowledgeClass,
  confidence: z.number().min(0).max(1).optional(),
  review_status: z.enum(["UNREVIEWED", "PROMOTED", "REJECTED"]),
  promoted_to_spec_id: Uuid.nullable().optional(),
});

export const BehavioralBaseline = z.object({
  id: Uuid,
  project_id: Uuid,
  key: z.string(),
  title: z.string(),
  repository_sha: z.string(),
  status: z.string(),
});

export const BaselineSet = z.object({
  id: Uuid,
  project_id: Uuid,
  key: z.string(),
  repository_sha: z.string(),
  baseline_ids: z.array(Uuid),
});

export const ReadinessAssessment = z.object({
  id: Uuid,
  project_id: Uuid,
  delivery_cycle_id: Uuid,
  state: z.string(),
  assessed_at: IsoDateTime,
  metrics: z.array(
    z.object({
      name: z.string(),
      value: z.number(),
      threshold: z.number(),
      ok: z.boolean(),
    }),
  ),
});

export const DiscoveryStep = z.object({
  step_key: z.string(),
  label: z.string(),
  status: z.enum(["PENDING", "RUNNING", "SUCCEEDED", "FAILED"]),
  started_at: IsoDateTime.nullable().optional(),
  finished_at: IsoDateTime.nullable().optional(),
});

export const RepositoryDiscovery = z.object({
  id: Uuid,
  delivery_cycle_id: Uuid,
  repository_id: Uuid,
  status: z.string(),
  commit_sha: z.string().nullable().optional(),
  content: z.record(z.string(), z.unknown()).nullable().optional(),
  steps: z.array(DiscoveryStep).optional(),
  started_at: IsoDateTime.optional(),
  finished_at: IsoDateTime.nullable().optional(),
});

export const ObservedBehavior = z.object({
  id: Uuid,
  key: z.string(),
  project_id: Uuid,
  delivery_cycle_id: Uuid,
  index_version_id: Uuid,
  commit_sha: z.string(),
  kind: z.string(),
  description: z.string(),
  subject_stable_keys: z.array(z.string()).optional(),
  evidence_refs: z.array(z.record(z.string(), z.unknown())).optional(),
  provenance: z.string().optional(),
  confidence: z.number().optional(),
  passed: z.boolean().nullable().optional(),
});

export const PromotionDecision = z.object({
  id: Uuid,
  delivery_cycle_id: Uuid,
  recovered_spec_id: Uuid,
  decision: z.enum(["PROMOTED", "REJECTED", "DEFERRED"]),
  note: z.string().nullable().optional(),
});
