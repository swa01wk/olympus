import { test } from "@playwright/test";

export type DiagCtx = {
  journey: string;
  stage: string;
  dimension: string;
};

export function diagStep(ctx: DiagCtx, expectation: string, fn: () => Promise<void>) {
  return test.step(`[${ctx.journey}][${ctx.stage}][${ctx.dimension}] ${expectation}`, fn);
}
