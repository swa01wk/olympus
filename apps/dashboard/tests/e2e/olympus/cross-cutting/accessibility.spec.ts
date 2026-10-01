import { test, expect } from "../fixtures/olympus.fixture";
import AxeBuilder from "@axe-core/playwright";
import { DELIVERY_CYCLES } from "../fixtures/journey-expectations";

test.describe("@frontend-e2e @transparency accessibility", () => {
  test("command center has no serious axe violations", async ({ page, scenario }) => {
    await scenario.gotoProjectCheckpoint("feature-change", "05-development-running", DELIVERY_CYCLES.featureChange);
    const results = await new AxeBuilder({ page })
      .disableRules(["color-contrast", "nested-interactive", "scrollable-region-focusable"])
      .analyze();
    const serious = results.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious",
    );
    expect(serious).toEqual([]);
  });

  test("status labels are visible text", async ({ page, scenario }) => {
    await scenario.gotoProjectCheckpoint("feature-change", "05-development-running", DELIVERY_CYCLES.featureChange);
    await expect(page.getByText("BLOCKED").first()).toBeVisible();
    await expect(page.getByText("RUNNING").first()).toBeVisible();
  });
});
