import { z } from "zod";

export const Uuid = z.string().uuid();
export const Sha = z.string().min(7);
export const IsoDateTime = z.string();

export const VersionedRef = z.object({
  ref_type: z.string(),
  ref_id: Uuid,
  version: z.number().int().nullable().optional(),
  key: z.string().nullable().optional(),
});

export const Page = <T extends z.ZodTypeAny>(item: T) =>
  z.object({
    items: z.array(item),
    next_after: z.number().int().nullable().optional(),
    total: z.number().int().optional(),
  });

export const ApiErrorBody = z.object({
  code: z.string().optional(),
  message: z.string().optional(),
  reasons: z.array(z.string()).optional(),
  current: z.string().optional(),
});

export type VersionedRef = z.infer<typeof VersionedRef>;
