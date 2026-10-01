import { z } from "zod";
import { IsoDateTime, Uuid } from "./common";

export const DomainEvent = z.object({
  id: Uuid,
  sequence: z.number().int(),
  event_type: z.string(),
  aggregate_type: z.string(),
  aggregate_id: Uuid,
  project_id: Uuid,
  delivery_cycle_id: Uuid.nullable().optional(),
  payload: z.record(z.string(), z.unknown()),
  correlation_id: z.string(),
  causation_id: z.string().nullable().optional(),
  actor_id: Uuid.nullable().optional(),
  occurred_at: IsoDateTime,
});
