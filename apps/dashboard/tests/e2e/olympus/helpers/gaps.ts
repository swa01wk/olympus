import { test } from "@playwright/test";

export function gapStep(gapId: string, reason: string, fn: () => Promise<void>) {
  return test.step(`[${gapId}] ${reason}`, async () => {
    test.info().annotations.push({ type: "gap", description: `${gapId}: ${reason}` });
    test.skip(true, reason);
    await fn();
  });
}
