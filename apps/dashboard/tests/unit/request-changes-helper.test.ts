import { describe, expect, it } from "vitest";
import {
  REQUEST_CHANGES_AGENT_HELPER,
  REQUEST_CHANGES_NO_REVISION_HELPER,
  requestChangesHelperText,
  type RequestChangesContext,
} from "@/lib/request-changes-helper";

function text(ctx: Partial<RequestChangesContext> & { approvalType: string }) {
  return requestChangesHelperText({
    cycleType: "GREENFIELD_BUILD",
    cycleState: "PRODUCT_MODEL",
    ...ctx,
  });
}

describe("requestChangesHelperText", () => {
  it("no-revision text never claims revision support is pending", () => {
    expect(REQUEST_CHANGES_NO_REVISION_HELPER).not.toMatch(/until revision support ships/);
  });

  it.each(["RELEASE", "FINDING_WAIVER", "ACTION", "PROMOTION", "UNREPRODUCED_REPAIR"])(
    "%s never revises",
    (approvalType) => {
      expect(text({ approvalType })).toBe(REQUEST_CHANGES_NO_REVISION_HELPER);
    },
  );

  it("SCOPE revises in DISCOVERY and PRODUCT_MODEL", () => {
    expect(text({ approvalType: "SCOPE", cycleState: "PRODUCT_MODEL" })).toBe(
      REQUEST_CHANGES_AGENT_HELPER,
    );
    expect(text({ approvalType: "SCOPE", cycleState: "DISCOVERY" })).toBe(
      REQUEST_CHANGES_AGENT_HELPER,
    );
  });

  it("SCOPE outside DISCOVERY / PRODUCT_MODEL does not revise", () => {
    expect(text({ approvalType: "SCOPE", cycleState: "ARCHITECTURE" })).toBe(
      REQUEST_CHANGES_NO_REVISION_HELPER,
    );
  });

  it("EXPECTED_BEHAVIOR revises on bug fix", () => {
    expect(text({ approvalType: "EXPECTED_BEHAVIOR", cycleType: "BUG_FIX" })).toBe(
      REQUEST_CHANGES_AGENT_HELPER,
    );
  });

  it("unknown types do not revise", () => {
    expect(text({ approvalType: "SOMETHING_NEW" })).toBe(REQUEST_CHANGES_NO_REVISION_HELPER);
  });

  it("ARCHITECTURE revises unless the subject is a delta", () => {
    expect(text({ approvalType: "ARCHITECTURE" })).toBe(REQUEST_CHANGES_AGENT_HELPER);
    expect(text({ approvalType: "ARCHITECTURE", subjectKind: "BASELINE" })).toBe(
      REQUEST_CHANGES_AGENT_HELPER,
    );
    expect(text({ approvalType: "ARCHITECTURE", subjectKind: "DELTA" })).toBe(
      REQUEST_CHANGES_NO_REVISION_HELPER,
    );
  });

  it("ARCHITECTURE_DELTA revises only for delta subjects", () => {
    expect(
      text({ approvalType: "ARCHITECTURE_DELTA", cycleType: "FEATURE_CHANGE", subjectKind: "DELTA" }),
    ).toBe(REQUEST_CHANGES_AGENT_HELPER);
    expect(
      text({ approvalType: "ARCHITECTURE_DELTA", cycleType: "FEATURE_CHANGE", subjectKind: "BASELINE" }),
    ).toBe(REQUEST_CHANGES_NO_REVISION_HELPER);
  });

  it("IMPLEMENTATION_SPEC revises except remediation", () => {
    expect(text({ approvalType: "IMPLEMENTATION_SPEC", cycleType: "BUG_FIX" })).toBe(
      REQUEST_CHANGES_AGENT_HELPER,
    );
    expect(
      text({ approvalType: "IMPLEMENTATION_SPEC", cycleType: "BROWNFIELD_ONBOARDING" }),
    ).toBe(REQUEST_CHANGES_NO_REVISION_HELPER);
    expect(text({ approvalType: "IMPLEMENTATION_SPEC", subjectKind: "REMEDIATION" })).toBe(
      REQUEST_CHANGES_NO_REVISION_HELPER,
    );
  });

  it("SPEC_DELTA revises", () => {
    expect(text({ approvalType: "SPEC_DELTA", cycleType: "FEATURE_CHANGE" })).toBe(
      REQUEST_CHANGES_AGENT_HELPER,
    );
  });
});
