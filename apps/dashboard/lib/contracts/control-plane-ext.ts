import { z } from "zod";
import { Uuid } from "./common";

export const ControlQuestionKind = z.enum([
  "TASK_BLOCKED",
  "INTEGRATION_UNAVAILABLE",
  "ACTION_DENIED",
  "GATE_FAILED",
  "RELEASE_BLOCKED",
]);

export const ControlConditionResult = z.object({
  name: z.string(),
  ok: z.boolean(),
  detail: z.string().optional(),
  refs: z
    .array(
      z.object({
        type: z.string(),
        id: Uuid.optional(),
        key: z.string().optional(),
        href: z.string().optional(),
      }),
    )
    .optional(),
});

/** @proposed M-35 */
export const ControlDecision = z.object({
  id: Uuid,
  question_kind: ControlQuestionKind,
  subject_type: z.string(),
  subject_id: Uuid,
  subject_key: z.string().optional(),
  outcome: z.string(),
  conditions: z.array(ControlConditionResult),
  source_endpoint: z.string().optional(),
});
