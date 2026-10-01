import { z } from "zod";
import { Uuid } from "./common";
import { SpecCodeLinkOrigin } from "./enums";

export const SpecCodeLink = z.object({
  id: Uuid,
  project_id: Uuid.optional(),
  repository_id: Uuid.optional(),
  index_version_id: Uuid,
  spec_type: z.enum(["FEATURE_SPEC", "IMPLEMENTATION_SPEC", "ACCEPTANCE_CRITERION"]),
  spec_id: Uuid,
  spec_lineage_key: z.string().optional(),
  spec_version: z.number().int(),
  entity_stable_key: z.string(),
  code_stable_key: z.string().optional(),
  relation: z.enum(["IMPLEMENTS", "VERIFIES"]),
  origin: SpecCodeLinkOrigin,
  confidence: z.number().min(0).max(1).nullable().optional(),
  task_id: Uuid.nullable().optional(),
  execution_id: Uuid.nullable().optional(),
  commit_sha: z.string().nullable().optional(),
  evidence_refs: z.array(z.record(z.string(), z.unknown())).optional(),
  established_index_version_id: Uuid.optional(),
  promoted_from_link_id: Uuid.nullable().optional(),
  status: z.enum(["ACTIVE", "STALE", "RETIRED", "SUPERSEDED"]),
});

export const LineageNode = z.object({
  type: z.string(),
  id: Uuid,
  key: z.string().optional(),
  version: z.number().int().optional(),
  label: z.string(),
  origin: SpecCodeLinkOrigin.optional(),
  confidence: z.number().optional(),
});

export const LineageEdge = z.object({
  from: Uuid,
  to: Uuid,
  relation: z.string(),
  origin: SpecCodeLinkOrigin.optional(),
  confidence: z.number().optional(),
});

export const LineageGraph = z.object({
  root_type: z.string(),
  root_id: Uuid,
  direction: z.enum(["FORWARD", "REVERSE"]),
  nodes: z.array(LineageNode),
  edges: z.array(LineageEdge),
});
