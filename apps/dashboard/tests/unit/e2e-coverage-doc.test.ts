import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

const COVERAGE_PATH = path.join(process.cwd(), "tests/e2e/olympus/COVERAGE.md");

describe("e2e COVERAGE.md sync", () => {
  it("documents four journeys and cross-cutting specs", () => {
    const md = fs.readFileSync(COVERAGE_PATH, "utf8");
    for (const token of [
      "feature-change.spec.ts",
      "greenfield.spec.ts",
      "brownfield.spec.ts",
      "bug-fix.spec.ts",
      "cross-cutting",
      "@fixture-journey",
    ]) {
      expect(md).toContain(token);
    }
  });
});
