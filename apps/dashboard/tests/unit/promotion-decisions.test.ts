import { describe, expect, it } from "vitest";
import {
  PROMOTION_DECISIONS_BY_SUBJECT_TYPE,
  defaultPromotionDecision,
  promotionDecisionAllowed,
  promotionDecisionRequiresApprover,
  promotionDecisionRequiresNote,
  promotionDecisionsForSubject,
} from "@/lib/promotion-decisions";

describe("PROMOTION_DECISIONS_BY_SUBJECT_TYPE", () => {
  it("FEATURE_SPEC", () => {
    expect(promotionDecisionsForSubject("FEATURE_SPEC")).toEqual([
      "PROMOTE_AS_CANONICAL",
      "CONFIRM_EXISTING",
      "REJECT_AS_NOT_INTENDED",
      "DEFER",
    ]);
  });

  it("ARCHITECTURE", () => {
    expect(promotionDecisionsForSubject("ARCHITECTURE")).toEqual([
      "APPROVE_AS_PROJECT_ARCHITECTURE",
    ]);
  });

  it("IMPLEMENTATION_SPEC", () => {
    expect(promotionDecisionsForSubject("IMPLEMENTATION_SPEC")).toEqual(["PROMOTE_AS_CANONICAL"]);
  });

  it("BASELINE", () => {
    expect(promotionDecisionsForSubject("BASELINE")).toEqual([
      "ACTIVATE",
      "REJECT_AS_NOT_INTENDED",
    ]);
  });

  it("UNCERTAINTY", () => {
    expect(promotionDecisionsForSubject("UNCERTAINTY")).toEqual(["RESOLVE", "ACCEPT_KNOWN_GAP"]);
  });

  it("covers every exported subject type", () => {
    expect(Object.keys(PROMOTION_DECISIONS_BY_SUBJECT_TYPE).sort()).toEqual(
      ["ARCHITECTURE", "BASELINE", "FEATURE_SPEC", "IMPLEMENTATION_SPEC", "UNCERTAINTY"].sort(),
    );
  });
});

describe("promotionDecisionRequiresApprover", () => {
  it("flags approver-only decisions", () => {
    expect(promotionDecisionRequiresApprover("PROMOTE_AS_CANONICAL")).toBe(true);
    expect(promotionDecisionRequiresApprover("APPROVE_AS_PROJECT_ARCHITECTURE")).toBe(true);
    expect(promotionDecisionRequiresApprover("ACCEPT_KNOWN_GAP")).toBe(true);
    expect(promotionDecisionRequiresApprover("CONFIRM_EXISTING")).toBe(false);
    expect(promotionDecisionRequiresApprover("ACTIVATE")).toBe(false);
  });
});

describe("promotionDecisionRequiresNote", () => {
  it("flags note-required decisions", () => {
    expect(promotionDecisionRequiresNote("REJECT_AS_NOT_INTENDED")).toBe(true);
    expect(promotionDecisionRequiresNote("DEFER")).toBe(true);
    expect(promotionDecisionRequiresNote("ACCEPT_KNOWN_GAP")).toBe(true);
    expect(promotionDecisionRequiresNote("PROMOTE_AS_CANONICAL")).toBe(false);
  });
});

describe("promotionDecisionAllowed", () => {
  it("allows everything for approvers and only non-approver decisions otherwise", () => {
    expect(promotionDecisionAllowed("PROMOTE_AS_CANONICAL", true)).toBe(true);
    expect(promotionDecisionAllowed("PROMOTE_AS_CANONICAL", false)).toBe(false);
    expect(promotionDecisionAllowed("CONFIRM_EXISTING", false)).toBe(true);
  });
});

describe("defaultPromotionDecision", () => {
  it("picks the first option the actor may use", () => {
    const options = promotionDecisionsForSubject("FEATURE_SPEC");
    expect(defaultPromotionDecision(options, true)).toBe("PROMOTE_AS_CANONICAL");
    expect(defaultPromotionDecision(options, false)).toBe("CONFIRM_EXISTING");
    expect(defaultPromotionDecision(promotionDecisionsForSubject("UNCERTAINTY"), false)).toBe(
      "RESOLVE",
    );
  });

  it("falls back to the first option when none are usable", () => {
    expect(defaultPromotionDecision(promotionDecisionsForSubject("ARCHITECTURE"), false)).toBe(
      "APPROVE_AS_PROJECT_ARCHITECTURE",
    );
    expect(defaultPromotionDecision([], false)).toBe("");
  });
});
