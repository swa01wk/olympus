import { z } from "zod";
import { IsoDateTime, Uuid } from "./common";

export const RepositorySourceType = z.enum(["GREENFIELD_MANAGED", "EXTERNAL_CLONE"]);
export const RepositoryProvider = z.enum([
  "LOCAL",
  "GITHUB",
  "GITEA",
  "GITLAB",
  "BITBUCKET",
]);
export const RepositoryStatus = z.enum([
  "PROVISIONING",
  "CLONING",
  "READY",
  "SYNCING",
  "ERROR",
]);
export const CredentialStatus = z.enum([
  "NOT_REQUIRED",
  "CONFIGURED",
  "MISSING",
  "INVALID",
]);
export const RepositoryWorkspaceState = z.enum([
  "PENDING",
  "MATERIALIZING",
  "READY",
  "REFRESHING",
  "MISSING",
  "ERROR",
]);
export const RevisionCause = z.enum([
  "MATERIALIZED",
  "INTEGRATION_READY",
  "RELEASED",
  "EXTERNAL_SYNC",
  "REVERTED",
]);
export const MaterializationKind = z.enum(["PROVISION", "CLONE", "FETCH"]);
export const MaterializationStatus = z.enum(["RUNNING", "SUCCEEDED", "FAILED"]);

/** @proposed key — human-readable repo key (REPO-001) */
export const Repository = z.object({
  id: Uuid,
  project_id: Uuid,
  key: z.string().optional(),
  name: z.string(),
  source_type: RepositorySourceType,
  provider: RepositoryProvider,
  remote_url: z.string().nullable().optional(),
  default_branch: z.string(),
  registered_sha: z.string().nullable().optional(),
  canonical_commit: z.string().nullable().optional(),
  released_commit: z.string().nullable().optional(),
  status: RepositoryStatus,
  workspace_id: Uuid,
  credential_ref: z.string().nullable().optional(),
  credential_status: CredentialStatus.optional(),
  created_at: IsoDateTime.optional(),
  updated_at: IsoDateTime.optional(),
});

export const RepositoryWorkspace = z.object({
  id: Uuid,
  repository_id: Uuid,
  key: z.string().optional(),
  workspace_type: z.literal("CANONICAL"),
  storage_backend: z.literal("LOCAL_FILESYSTEM"),
  logical_location: z.string(),
  materialized_commit: z.string().nullable().optional(),
  state: RepositoryWorkspaceState,
  created_at: IsoDateTime.optional(),
  updated_at: IsoDateTime.optional(),
});

export const RepositoryRevision = z.object({
  id: Uuid,
  repository_id: Uuid,
  sequence: z.number().int(),
  commit_sha: z.string(),
  cause: RevisionCause,
  integration_candidate_id: Uuid.nullable().optional(),
  release_id: Uuid.nullable().optional(),
  repository_event_id: Uuid.nullable().optional(),
  canonical_index_version_id: Uuid.nullable().optional(),
  actor_id: Uuid.nullable().optional(),
  correlation_id: z.string().nullable().optional(),
  created_at: IsoDateTime,
});

/** @proposed M-30 steps[] and progress on materialization read model */
export const MaterializationStep = z.object({
  step_key: z.string(),
  label: z.string(),
  status: z.enum(["PENDING", "RUNNING", "SUCCEEDED", "FAILED"]),
  started_at: IsoDateTime.nullable().optional(),
  finished_at: IsoDateTime.nullable().optional(),
  detail: z.string().nullable().optional(),
});

export const RepositoryMaterialization = z.object({
  id: Uuid,
  repository_id: Uuid,
  kind: MaterializationKind,
  attempt: z.number().int(),
  status: MaterializationStatus,
  action_request_ids: z.array(Uuid).optional(),
  resulting_sha: z.string().nullable().optional(),
  observed_default_branch: z.string().nullable().optional(),
  error_class: z.string().nullable().optional(),
  error_detail: z.string().nullable().optional(),
  started_at: IsoDateTime,
  finished_at: IsoDateTime.nullable().optional(),
  steps: z.array(MaterializationStep).optional(),
  progress: z
    .object({
      objects_received: z.number().int().optional(),
      objects_total: z.number().int().optional(),
      bytes_received: z.number().int().optional(),
    })
    .optional(),
});

export const CommitLedgerEntry = z.object({
  kind: z.enum(["CANONICAL_REVISION", "CANDIDATE", "INTEGRATION_MERGE"]),
  sha: z.string(),
  label: z.string().optional(),
  sequence: z.number().int().nullable().optional(),
  cause: RevisionCause.nullable().optional(),
  execution_key: z.string().nullable().optional(),
  task_key: z.string().nullable().optional(),
  branch: z.string().nullable().optional(),
  base_sha: z.string().nullable().optional(),
  integration_candidate_key: z.string().nullable().optional(),
  included_in_ic: z.boolean().nullable().optional(),
  created_at: IsoDateTime.optional(),
});
