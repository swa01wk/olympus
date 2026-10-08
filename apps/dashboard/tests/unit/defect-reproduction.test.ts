import { describe, expect, it } from "vitest";
import { mayProceedUnreproduced, mayRejectDefect } from "@/lib/defect-reproduction";

describe("mayProceedUnreproduced", () => {
  it("true when defect is NOT_REPRODUCIBLE", () => {
    expect(mayProceedUnreproduced("NOT_REPRODUCIBLE", [])).toBe(true);
  });

  it("true when all PRE_REPAIR attempts failed", () => {
    expect(
      mayProceedUnreproduced("TRIAGED", [
        { phase: "PRE_REPAIR", outcome: "NOT_REPRODUCED" },
        { phase: "PRE_REPAIR", outcome: "FAIL" },
      ]),
    ).toBe(true);
  });

  it("false when a reproduction succeeded", () => {
    expect(
      mayProceedUnreproduced("TRIAGED", [{ phase: "PRE_REPAIR", outcome: "REPRODUCED" }]),
    ).toBe(false);
  });
});

describe("mayRejectDefect", () => {
  it("false for terminal statuses", () => {
    expect(mayRejectDefect("REJECTED")).toBe(false);
    expect(mayRejectDefect("RELEASED")).toBe(false);
  });

  it("true for active triage", () => {
    expect(mayRejectDefect("TRIAGED")).toBe(true);
  });
});
