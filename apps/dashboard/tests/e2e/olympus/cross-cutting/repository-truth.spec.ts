import { test, expect } from "../fixtures/olympus.fixture";
import { DELIVERY_CYCLES, SHA } from "../fixtures/journey-expectations";

test.describe("@frontend-e2e @transparency @repository", () => {
  test("before integration canonical stays r1 at FC development", async ({ page, scenario }) => {
    await scenario.gotoProjectCheckpoint("feature-change", "05-development-running", DELIVERY_CYCLES.featureChange);
    await page.getByRole("navigation", { name: "Project navigation" }).getByRole("link", { name: "Code" }).click();
    await expect(page.locator(`[data-sha="${SHA.r1.full}"]`).first()).toBeVisible();
  });

  test("after reindex canonical is r2", async ({ page, scenario }) => {
    await scenario.gotoProjectCheckpoint("feature-change", "08-canonical-reindex", DELIVERY_CYCLES.featureChange);
    await page.getByRole("navigation", { name: "Project navigation" }).getByRole("link", { name: "Code" }).click();
    await expect(page.locator(`[data-sha="${SHA.r2.full}"]`).first()).toBeVisible();
  });
});
