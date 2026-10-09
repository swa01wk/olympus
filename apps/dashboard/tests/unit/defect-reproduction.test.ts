import { describe, expect, it } from "vitest";
import {
  mayProceedUnreproduced,
  mayRejectDefect,
  policyAllowsUnreproduced,
  policyValue,
} from "@/lib/defect-reproduction";

describe("mayProceedUnreproduced", () => {
  it("true when defect is NOT_REPRODUCIBLE", () => {
    expect(mayProceedUnreproduced("NOT_REPRODUCIBLE")).toBe(true);
  });

  it("false for any other status", () => {
    expect(mayProceedUnreproduced("TRIAGED")).toBe(false);
    expect(mayProceedUnreproduced("REPRODUCED")).toBe(false);
    expect(mayProceedUnreproduced("EXPECTED_RESOLVED")).toBe(false);
  });
});

describe("policy lookup", () => {
  it("reads dotted paths into nested policy content", () => {
    const content = { bugfix: { reproduction_attempts: 3, allow_unreproduced: true } };
    expect(policyValue(content, "bugfix.reproduction_attempts")).toBe(3);
    expect(policyValue(content, "bugfix.missing")).toBeUndefined();
    expect(policyValue(content, "nope.deeper")).toBeUndefined();
  });

  it("policyAllowsUnreproduced follows bugfix.allow_unreproduced, defaulting to false", () => {
    expect(policyAllowsUnreproduced({ bugfix: { allow_unreproduced: true } })).toBe(true);
    expect(policyAllowsUnreproduced({ bugfix: { allow_unreproduced: false } })).toBe(false);
    expect(policyAllowsUnreproduced({})).toBe(false);
  });
});

describe("mayRejectDefect", () => {
  it("false for terminal statuses", () => {
    expect(mayRejectDefect("REJECTED")).toBe(false);
    expect(mayRejectDefect("FIXED")).toBe(false);
    expect(mayRejectDefect("RELEASED")).toBe(false);
  });

  it("true for active statuses", () => {
    expect(mayRejectDefect("TRIAGED")).toBe(true);
    expect(mayRejectDefect("NOT_REPRODUCIBLE")).toBe(true);
    expect(mayRejectDefect("EXPECTED_RESOLVED")).toBe(true);
  });
});
