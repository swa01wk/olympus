import { z } from "zod";
import { IsoDateTime, Uuid } from "./common";

export const ExecutionLease = z.object({
  execution_id: Uuid,
  worker_id: z.string(),
  heartbeat_at: IsoDateTime,
  expires_at: IsoDateTime,
  state: z.string(),
});

export const ModelCall = z.object({
  id: Uuid,
  execution_id: Uuid,
  model_alias: z.string(),
  provider: z.string().nullable().optional(),
  input_tokens: z.number().int().optional(),
  output_tokens: z.number().int().optional(),
  cost_usd: z.number().nullable().optional(),
  latency_ms: z.number().int().optional(),
  prompt_hash: z.string().nullable().optional(),
  created_at: IsoDateTime.optional(),
});

export const Artifact = z.object({
  id: Uuid,
  key: z.string().optional(),
  project_id: Uuid,
  delivery_cycle_id: Uuid.nullable().optional(),
  execution_id: Uuid.nullable().optional(),
  kind: z.string(),
  schema_name: z.string().nullable().optional(),
  content_hash: z.string(),
  size_bytes: z.number().int().optional(),
  storage_ref: z.string().nullable().optional(),
  created_at: IsoDateTime.optional(),
});

/** M-27 + @proposed M-40 current_action / current_resource */
export const RuntimeMetadata = z.object({
  execution_id: Uuid,
  runtime: z.string().nullable().optional(),
  model_alias: z.string().nullable().optional(),
  current_action_id: Uuid.nullable().optional(),
  current_resource: z.string().nullable().optional(),
});
