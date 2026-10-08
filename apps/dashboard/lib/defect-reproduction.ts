/** When the UI may offer proceed-unreproduced (matches cycle stuck in REPRODUCTION). */

export type ReproductionSummary = {
  phase?: string;
  outcome?: string;
};

export function mayProceedUnreproduced(
  defectStatus: string,
  reproductions: ReproductionSummary[],
): boolean {
  if (defectStatus === "NOT_REPRODUCIBLE") return true;
  const preRepair = reproductions.filter((r) => r.phase === "PRE_REPAIR");
  if (preRepair.length === 0) return false;
  return preRepair.every(
    (r) => r.outcome === "NOT_REPRODUCED" || r.outcome === "FAIL",
  );
}

export function mayRejectDefect(defectStatus: string): boolean {
  return !["REJECTED", "RELEASED", "CANCELLED"].includes(defectStatus);
}
