import { describe, expect, it } from "vitest";
import { buildMacroBands } from "@/lib/view-models/macro-forge";

describe("buildMacroBands", () => {
  it("groups FEATURE_CHANGE journey into macro bands", () => {
    const bands = buildMacroBands("FEATURE_CHANGE", "DEVELOPMENT", [], { runningExecutions: 2 });
    const ids = bands.map((b) => b.id);
    expect(ids).toContain("DEVELOPMENT");
    expect(ids).toContain("INTAKE");
    const dev = bands.find((b) => b.id === "DEVELOPMENT");
    expect(dev?.display).toBe("ACTIVE");
  });
});
