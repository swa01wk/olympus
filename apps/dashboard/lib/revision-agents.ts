/** Display name for the producing agent during revision (RL2.3). */

export function revisingAgentLabel(subjectType: string): string {
  const t = subjectType.toLowerCase();
  if (t === "scope_set" || t === "product_source" || t === "spec_delta") {
    return "Kira";
  }
  return "Atlas";
}
