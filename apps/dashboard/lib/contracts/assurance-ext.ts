import { z } from "zod";
import { IsoDateTime, Uuid } from "./common";

export const EvidenceType = z.enum([
  "UNIT_TEST",
  "INTEGRATION_TEST",
  "API_TEST",
  "E2E_TEST",
  "REGRESSION_TEST",
  "REPRODUCTION",
  "RUNTIME_OBSERVATION",
  "STATIC_REVIEW",
  "MODEL_ASSESSMENT",
  "EXTERNAL_CI",
  "INTEGRATION_CHECK",
]);

export const Evidence = z.object({
  id: Uuid,
  key: z.string(),
  project_id: Uuid,
  delivery_cycle_id: Uuid,
  integration_candidate_id: Uuid.nullable().optional(),
  commit_sha: z.string(),
  evidence_type: EvidenceType,
  result: z.enum(["PASS", "FAIL", "ERROR", "SKIPPED"]),
  subject_type: z.string(),
  subject_id: Uuid,
  subject_key: z.string().optional(),
  obligation_id: Uuid.nullable().optional(),
  check_ref: z.string().nullable().optional(),
  check_artifact_id: Uuid.nullable().optional(),
  producer: z.string(),
  execution_id: Uuid.nullable().optional(),
  details: z.record(z.string(), z.unknown()).optional(),
  created_at: IsoDateTime.optional(),
});

export const VerificationObligation = z.object({
  id: Uuid,
  delivery_cycle_id: Uuid,
  integration_candidate_id: Uuid,
  gate_type: z.string(),
  subject_type: z.string(),
  subject_id: Uuid,
  subject_key: z.string(),
  required: z.boolean(),
  allowed_evidence_types: z.array(z.string()).optional(),
  reason: z.string(),
  status: z.enum(["OPEN", "SATISFIED", "FAILED", "WAIVED"]),
});

export const AcceptanceCoverage = z.object({
  obligation_id: Uuid,
  evidence_id: Uuid.nullable().optional(),
  satisfied: z.boolean(),
  computed_at: IsoDateTime,
});

export const Review = z.object({
  id: Uuid,
  integration_candidate_id: Uuid,
  execution_id: Uuid.nullable().optional(),
  recommendation: z.string().nullable().optional(),
  summary: z.string().nullable().optional(),
  artifact_id: Uuid.nullable().optional(),
});
