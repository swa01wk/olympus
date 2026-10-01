import { z } from "zod";
import { Uuid, VersionedRef } from "./common";
import { KnowledgeClass } from "./enums";

export const ProductSource = z.object({
  id: Uuid,
  project_id: Uuid,
  key: z.string(),
  title: z.string(),
  source_kind: z.string(),
  version: z.number().int(),
});

export const Capability = z.object({
  id: Uuid,
  project_id: Uuid,
  key: z.string(),
  title: z.string(),
});

export const Feature = z.object({
  id: Uuid,
  project_id: Uuid,
  capability_id: Uuid,
  key: z.string(),
  title: z.string(),
});

export const FeatureSpec = z.object({
  id: Uuid,
  feature_id: Uuid,
  key: z.string(),
  version: z.number().int(),
  status: z.string(),
  title: z.string(),
  knowledge_class: KnowledgeClass.optional(),
});

export const AcceptanceCriterion = z.object({
  id: Uuid,
  feature_spec_id: Uuid,
  key: z.string(),
  statement: z.string(),
  version: z.number().int(),
  mandatory: z.boolean().optional(),
});

export const Requirement = z.object({
  id: Uuid,
  feature_spec_id: Uuid,
  key: z.string(),
  statement: z.string(),
  kind: z.enum(["FUNCTIONAL", "NON_FUNCTIONAL", "CONSTRAINT"]).optional(),
  priority: z.enum(["MUST", "SHOULD", "COULD"]).optional(),
  version: z.number().int(),
});

export const UserStory = z.object({
  id: Uuid,
  feature_spec_id: Uuid,
  key: z.string(),
  actor: z.string(),
  goal: z.string(),
  benefit: z.string(),
  version: z.number().int(),
});

export const KnowledgeItem = z.object({
  id: Uuid,
  project_id: Uuid,
  delivery_cycle_id: Uuid.nullable().optional(),
  key: z.string().optional(),
  class: z.string(),
  statement: z.string(),
  subject_refs: z.array(z.record(z.string(), z.unknown())).optional(),
  provenance: z.record(z.string(), z.unknown()).optional(),
  evidence_refs: z.array(z.record(z.string(), z.unknown())).optional(),
  confidence: z.enum(["HIGH", "MEDIUM", "LOW", "NULL"]).nullable().optional(),
  status: z.enum(["ACTIVE", "SUPERSEDED", "REJECTED"]).optional(),
  blocking: z.boolean().optional(),
});
