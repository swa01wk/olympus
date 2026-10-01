import { describe, expect, it } from "vitest";
import { humanizeReason } from "@/lib/view-models/reason-code";

describe("humanizeReason", () => {
  it("expands dependency incomplete codes", () => {
    expect(humanizeReason("DEPENDENCY_INCOMPLETE:TASK-222")).toContain("TASK-222");
  });

  it("maps known prefixes", () => {
    expect(humanizeReason("NOT_READY")).toContain("not in a ready state");
  });

  it("returns raw code when unknown", () => {
    expect(humanizeReason("CUSTOM:foo")).toBe("CUSTOM:foo");
  });
});
