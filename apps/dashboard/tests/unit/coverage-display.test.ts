import { describe, expect, it } from "vitest";
import { coverageRowsForDisplay } from "@/lib/coverage-display";

describe("coverageRowsForDisplay", () => {
  it("hides aggregate percent fields (G6)", () => {
    const rows = coverageRowsForDisplay({
      project_id: "p1",
      acceptance_criterion_count: 10,
      acceptance_criteria_with_evidence_pct: 42.5,
      verification_obligations: 3,
    });
    expect(rows.some(([k]) => k.includes("pct"))).toBe(false);
    expect(rows).toContainEqual(["acceptance criterion count", "10"]);
  });
});
