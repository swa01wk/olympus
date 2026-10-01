/** Human-readable line for eligibility / guard reason codes (presentation only). */
export function humanizeReason(code: string): string {
  if (code.startsWith("DEPENDENCY_INCOMPLETE:")) {
    const dep = code.split(":")[1];
    return `Dependency ${dep ?? "unknown"} is not complete.`;
  }
  const map: Record<string, string> = {
    NOT_READY: "Task is not in a ready state.",
    ARTIFACT_MISSING: "Required artifact is missing.",
    CONTRACT_VERSION_MISMATCH: "Task contract version does not match.",
    APPROVAL_MISSING: "Required approval is missing.",
    POLICY_BLOCKED: "Policy blocked this work.",
    CONFLICTING_EXECUTION: "Another execution is in progress.",
    BASE_RESOLVER_UNAVAILABLE: "Base commit resolver unavailable.",
  };
  for (const [prefix, msg] of Object.entries(map)) {
    if (code.startsWith(prefix)) return msg;
  }
  return code;
}
