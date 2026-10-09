/** Decisions accepted by `PromotionService.decide` per subject_type (read from backend branches). */

export type PromotionSubjectType =
  | "FEATURE_SPEC"
  | "ARCHITECTURE"
  | "IMPLEMENTATION_SPEC"
  | "BASELINE"
  | "UNCERTAINTY";

export const PROMOTION_DECISIONS_BY_SUBJECT_TYPE: Record<
  PromotionSubjectType,
  readonly string[]
> = {
  FEATURE_SPEC: [
    "PROMOTE_AS_CANONICAL",
    "CONFIRM_EXISTING",
    "REJECT_AS_NOT_INTENDED",
    "DEFER",
  ],
  ARCHITECTURE: ["APPROVE_AS_PROJECT_ARCHITECTURE"],
  IMPLEMENTATION_SPEC: ["PROMOTE_AS_CANONICAL"],
  BASELINE: ["ACTIVATE", "REJECT_AS_NOT_INTENDED"],
  UNCERTAINTY: ["RESOLVE", "ACCEPT_KNOWN_GAP"],
};

const APPROVER_DECISIONS = new Set([
  "PROMOTE_AS_CANONICAL",
  "APPROVE_AS_PROJECT_ARCHITECTURE",
  "ACCEPT_KNOWN_GAP",
]);

const NOTE_REQUIRED_DECISIONS = new Set([
  "REJECT_AS_NOT_INTENDED",
  "DEFER",
  "ACCEPT_KNOWN_GAP",
]);

export function promotionDecisionsForSubject(subjectType: string): readonly string[] {
  return PROMOTION_DECISIONS_BY_SUBJECT_TYPE[subjectType as PromotionSubjectType] ?? [];
}

export function promotionDecisionRequiresApprover(decision: string): boolean {
  return APPROVER_DECISIONS.has(decision);
}

export function promotionDecisionRequiresNote(decision: string): boolean {
  return NOTE_REQUIRED_DECISIONS.has(decision);
}

export function promotionDecisionAllowed(decision: string, canApprove: boolean): boolean {
  return canApprove || !promotionDecisionRequiresApprover(decision);
}

/** First option the actor may use; the first option when none are usable. */
export function defaultPromotionDecision(
  options: readonly string[],
  canApprove: boolean,
): string {
  return options.find((d) => promotionDecisionAllowed(d, canApprove)) ?? options[0] ?? "";
}
