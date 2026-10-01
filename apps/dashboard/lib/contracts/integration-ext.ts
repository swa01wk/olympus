import { z } from "zod";
import { Uuid } from "./common";

export const IntegrationCandidateCommit = z.object({
  id: Uuid.optional(),
  integration_candidate_id: Uuid,
  candidate_commit_id: Uuid,
  candidate_commit_sha: z.string().optional(),
  position: z.number().int(),
  included: z.boolean(),
  skip_reason: z.string().nullable().optional(),
  task_key: z.string().nullable().optional(),
  execution_key: z.string().nullable().optional(),
});
