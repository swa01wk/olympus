import { z } from "zod";
import { IsoDateTime, Uuid } from "./common";

export const ConnectorConfig = z.object({
  id: Uuid,
  project_id: Uuid,
  connector_type: z.string(),
  name: z.string(),
  status: z.string(),
});

export const InboundEvent = z.object({
  id: Uuid,
  project_id: Uuid,
  source: z.string(),
  event_type: z.string(),
  status: z.string(),
  received_at: IsoDateTime,
  correlation_id: z.string().optional(),
});

export const ConnectorAction = z.object({
  id: Uuid,
  connector_id: Uuid,
  action_type: z.string(),
  status: z.string(),
  idempotency_key: z.string(),
  correlation_id: z.string().optional(),
});

export const ChangeRequest = z.object({
  id: Uuid,
  project_id: Uuid,
  delivery_cycle_id: Uuid.nullable().optional(),
  key: z.string(),
  title: z.string(),
  source: z.string(),
  status: z.string(),
});
