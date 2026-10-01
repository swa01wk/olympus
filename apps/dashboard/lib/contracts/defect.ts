import { z } from "zod";
import { IsoDateTime, Uuid } from "./common";
import { KnowledgeClass } from "./enums";

export const Defect = z.object({
  id: Uuid,
  project_id: Uuid,
  delivery_cycle_id: Uuid,
  key: z.string(),
  title: z.string(),
  status: z.string(),
  severity: z.string(),
});

export const Reproduction = z.object({
  id: Uuid,
  defect_id: Uuid,
  phase: z.enum(["PRE_FIX", "POST_FIX"]),
  status: z.string(),
  steps: z.array(z.string()),
  observed_at: IsoDateTime.optional(),
});

export const TraceCorrelation = z.object({
  id: Uuid,
  defect_id: Uuid,
  delivery_cycle_id: Uuid,
  candidates: z.array(
    z.object({
      stable_key: z.string(),
      evidence_basis: z.string(),
      path: z.array(z.string()),
    }),
  ),
});

export const RootCauseAnalysis = z.object({
  id: Uuid,
  defect_id: Uuid,
  knowledge_class: KnowledgeClass,
  summary: z.string(),
  contributing_factors: z.array(z.string()),
});
