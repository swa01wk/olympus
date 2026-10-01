import { z } from "zod";

/** Strict in tests/fixtures; permissive at runtime for live API drift tolerance. */
export function openEnum<T extends readonly [string, ...string[]]>(
  values: T,
  label: string,
) {
  const strict = z.enum(values);
  return z
    .string()
    .transform((val, ctx) => {
      if ((values as readonly string[]).includes(val)) return val as T[number];
      if (process.env.NODE_ENV === "test") {
        ctx.addIssue({ code: "custom", message: `Unknown ${label}: ${val}` });
        return z.NEVER;
      }
      if (typeof console !== "undefined") {
        console.warn(`[olympus] unknown ${label}: ${val}`);
      }
      return val;
    });
}

export function strictEnum<T extends readonly [string, ...string[]]>(values: T) {
  return z.enum(values);
}
