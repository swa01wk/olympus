/** S01 truth rule G6: show denominators, hide aggregate completion %. */

const HIDDEN_COVERAGE_KEYS = new Set([
  "acceptance_criteria_with_evidence_pct",
  "project_id",
]);

export type CoverageRow = [label: string, value: string];

export function coverageRowsForDisplay(data: Record<string, unknown>): CoverageRow[] {
  const rows: CoverageRow[] = [];
  for (const [key, value] of Object.entries(data)) {
    if (HIDDEN_COVERAGE_KEYS.has(key)) continue;
    if (typeof value === "object" && value !== null) continue;
    if (key.endsWith("_pct") || key.includes("percent")) continue;
    rows.push([formatCoverageKey(key), String(value)]);
  }
  return rows;
}

function formatCoverageKey(key: string): string {
  return key.replace(/_/g, " ");
}
