import { z } from "zod";
import { IsoDateTime, Uuid } from "./common";
import { IndexKind } from "./enums";

export const EntityType = z.enum([
  "REPOSITORY",
  "PACKAGE",
  "MODULE",
  "FILE",
  "CLASS",
  "METHOD",
  "FUNCTION",
  "ROUTE",
  "SCHEMA",
  "ORM_MODEL",
  "TABLE",
  "TEST",
]);

export const CodeIndexVersion = z.object({
  id: Uuid,
  repository_id: Uuid,
  key: z.string().optional(),
  commit_sha: z.string(),
  kind: IndexKind,
  source: z.string(),
  scope_ref: z.string(),
  status: z.string(),
  built_at: IsoDateTime.optional(),
});

export const CodeEntity = z.object({
  id: Uuid,
  index_version_id: Uuid,
  stable_key: z.string(),
  type: EntityType,
  language: z.string().default("python"),
  name: z.string(),
  qualified_name: z.string().optional(),
  file_path: z.string().nullable().optional(),
  start_line: z.number().int().nullable().optional(),
  end_line: z.number().int().nullable().optional(),
});

export const CodeRelation = z.object({
  id: Uuid,
  index_version_id: Uuid,
  from_entity_id: Uuid,
  to_entity_id: Uuid,
  relation: z.string(),
  provenance: z.string().optional(),
  confidence: z.number().min(0).max(1).optional(),
});

export const IndexPointer = z.object({
  repository_id: Uuid,
  canonical_index_version_id: Uuid,
  released_commit_sha: z.string().nullable().optional(),
});

export const CodeEntityChange = z.object({
  id: Uuid,
  repository_id: Uuid.optional(),
  from_index_version_id: Uuid.nullable().optional(),
  to_index_version_id: Uuid.nullable().optional(),
  entity_stable_key: z.string(),
  change_kind: z.string(),
  execution_id: Uuid.nullable().optional(),
  task_id: Uuid.nullable().optional(),
  candidate_commit_sha: z.string().nullable().optional(),
  integration_candidate_id: Uuid.nullable().optional(),
  integrated_sha: z.string().nullable().optional(),
});

export const RetrievalHit = z.object({
  entity_id: Uuid,
  stable_key: z.string(),
  type: EntityType,
  score: z.number(),
  retrieval_source: z.enum(["STRUCTURAL", "LEXICAL", "SEMANTIC"]),
});
