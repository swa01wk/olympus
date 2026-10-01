import { z } from "zod";
import { Uuid } from "./common";

/** @proposed M-26 */
export const ProjectSummaryView = z.object({
  project_id: Uuid,
  active_cycle_id: Uuid.nullable().optional(),
  active_cycle_key: z.string().nullable().optional(),
  stage: z.string().nullable().optional(),
  task_count: z.number().int(),
  running_executions: z.number().int(),
  canonical_sha: z.string().nullable().optional(),
  current_release_key: z.string().nullable().optional(),
});

/** @proposed M-16 */
export const CycleOverviewView = z.object({
  delivery_cycle_id: Uuid,
  key: z.string(),
  state: z.string(),
  running_executions: z.number().int(),
  blocked_tasks: z.number().int(),
  pending_approvals: z.number().int(),
  integration_candidate_key: z.string().nullable().optional(),
});

/** @proposed M-22 */
export const ControlPlaneView = z.object({
  delivery_cycle_id: Uuid,
  scheduler: z.record(z.string(), z.unknown()),
  execution_manager: z.record(z.string(), z.unknown()),
  policy: z.record(z.string(), z.unknown()),
  integration: z.record(z.string(), z.unknown()),
  assurance: z.record(z.string(), z.unknown()),
  release: z.record(z.string(), z.unknown()),
});
