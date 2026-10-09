/** When the UI may offer proceed-unreproduced (mirrors DefectService.proceed_unreproduced). */

const TERMINAL_DEFECT_STATUSES = new Set(["REJECTED", "FIXED", "RELEASED"]);

export function mayProceedUnreproduced(defectStatus: string): boolean {
  return defectStatus === "NOT_REPRODUCIBLE";
}

/** Dotted-path lookup into policy content, like PolicyService.get. */
export function policyValue(content: Record<string, unknown>, path: string): unknown {
  let node: unknown = content;
  for (const part of path.split(".")) {
    if (node == null || typeof node !== "object" || !(part in node)) return undefined;
    node = (node as Record<string, unknown>)[part];
  }
  return node;
}

export function policyAllowsUnreproduced(content: Record<string, unknown>): boolean {
  return Boolean(policyValue(content, "bugfix.allow_unreproduced"));
}

export function mayRejectDefect(defectStatus: string): boolean {
  return !TERMINAL_DEFECT_STATUSES.has(defectStatus);
}
