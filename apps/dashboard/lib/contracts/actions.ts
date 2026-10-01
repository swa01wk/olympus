import { z } from "zod";
import { IsoDateTime, Uuid } from "./common";
import { ActionStatus } from "./enums";

export const PolicyDecision = z.object({
  decision: z.enum(["ALLOW", "DENY", "REQUIRE_APPROVAL"]),
  rule_ids: z.array(z.string()).optional(),
  reasons: z.array(z.string()).optional(),
  policy_version_id: z.string().nullable().optional(),
});

export const ActionRequest = z.object({
  id: Uuid,
  key: z.string().optional(),
  project_id: Uuid,
  delivery_cycle_id: Uuid.nullable().optional(),
  execution_id: Uuid.nullable().optional(),
  task_id: Uuid.nullable().optional(),
  tool: z.string(),
  resource: z.string(),
  action: z.string(),
  params: z.record(z.string(), z.unknown()).optional(),
  status: ActionStatus,
  policy_decision: PolicyDecision.optional(),
  approval_id: Uuid.nullable().optional(),
  correlation_id: z.string().optional(),
  requested_at: IsoDateTime.optional(),
  completed_at: IsoDateTime.nullable().optional(),
});

export const ActionResult = z.object({
  id: Uuid,
  action_request_id: Uuid,
  status: z.enum(["SUCCEEDED", "FAILED"]),
  output: z.record(z.string(), z.unknown()).optional(),
  error: z.string().nullable().optional(),
});

/** @deprecated use ExecutionWorkspace — path removed (logical location only) */
export const Worktree = z.object({
  execution_id: Uuid,
  path: z.string().optional(),
  branch: z.string(),
  base_sha: z.string(),
  mode: z.string(),
  status: z.string(),
  logical_location: z.string().optional(),
});

export const ExecutionWorkspace = z.object({
  id: Uuid,
  key: z.string().optional(),
  execution_id: Uuid,
  repository_id: Uuid,
  type: z.literal("GIT_WORKTREE"),
  mode: z.enum(["WRITABLE", "READONLY"]),
  base_commit: z.string(),
  logical_location: z.string(),
  branch: z.string().nullable().optional(),
  state: z.enum(["CREATING", "ACTIVE", "RETAINED", "REMOVED", "ORPHANED"]),
  uncommitted_files: z
    .array(
      z.object({
        path: z.string(),
        change_type: z.string(),
      }),
    )
    .optional(),
  created_at: z.string().optional(),
  removed_at: z.string().nullable().optional(),
});

export const CandidateCommit = z.object({
  id: Uuid.optional(),
  key: z.string().optional(),
  sha: z.string(),
  parent_sha: z.string().nullable().optional(),
  base_sha: z.string(),
  execution_id: Uuid.optional(),
  task_id: Uuid.optional(),
  repository_id: Uuid.optional(),
  branch: z.string().optional(),
  diff_artifact_id: Uuid.nullable().optional(),
  changed_files: z.array(
    z.object({
      path: z.string(),
      change_type: z.string(),
      additions: z.number().int(),
      deletions: z.number().int(),
    }),
  ),
});
