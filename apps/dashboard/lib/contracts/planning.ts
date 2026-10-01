import { z } from "zod";
import { Uuid } from "./common";

export const Architecture = z.object({
  id: Uuid,
  project_id: Uuid,
  delivery_cycle_id: Uuid.nullable().optional(),
  key: z.string(),
  version: z.number().int(),
  status: z.string(),
});

export const ImplementationSpec = z.object({
  id: Uuid,
  project_id: Uuid,
  delivery_cycle_id: Uuid,
  key: z.string(),
  version: z.number().int(),
  status: z.string(),
  title: z.string(),
  feature_spec_refs: z.array(z.string()).optional(),
});

export const TaskPlan = z.object({
  id: Uuid,
  delivery_cycle_id: Uuid,
  version: z.number().int(),
  status: z.string(),
});
