import { z } from "zod";
import { Uuid } from "./common";
import { ImpactKind } from "./enums";

export const ImpactItem = z.object({
  id: Uuid,
  stable_key: z.string(),
  kind: ImpactKind,
  path: z.array(
    z.object({
      from: z.string(),
      relation: z.string(),
      to: z.string(),
    }),
  ),
});

export const ImpactAssessment = z.object({
  id: Uuid,
  delivery_cycle_id: Uuid,
  change_request_id: Uuid.nullable().optional(),
  feature_spec_id: Uuid,
  status: z.string(),
  items: z.array(ImpactItem),
});

export const SpecDelta = z.object({
  id: Uuid,
  feature_spec_id: Uuid,
  from_version: z.number().int(),
  to_version: z.number().int(),
  summary: z.string(),
});
