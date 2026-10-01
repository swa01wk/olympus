import { describe, expect, it } from "vitest";

describe("fixture production guard", () => {
  it("loads next config in test environment", async () => {
    await expect(import("../../next.config")).resolves.toBeDefined();
  });

  it("documents production guard condition", () => {
    const isProd = process.env.NODE_ENV === "production";
    const dataMode = process.env.NEXT_PUBLIC_OLYMPUS_DATA_MODE ?? "fixture";
    const demo = process.env.OLYMPUS_DEMO_BUILD === "1";
    const wouldThrow = isProd && dataMode === "fixture" && !demo;
    expect(wouldThrow).toBe(false);
  });
});
