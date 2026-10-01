import { test, expect } from "../fixtures/olympus.fixture";
import { DELIVERY_CYCLES } from "../fixtures/journey-expectations";

test.describe("@frontend-e2e @transparency @execution", () => {
  test("execution page shows EX-551 context", async ({ page, scenario }) => {
    await scenario.gotoProjectCheckpoint("feature-change", "05-development-running", DELIVERY_CYCLES.featureChange);
    await page.getByRole("navigation", { name: "Project navigation" }).getByRole("link", { name: "Executions" }).click();
    await page.getByRole("link", { name: /EX-551/ }).first().click();
    await expect(page.getByText("TASK-221").first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/TC-221|implementation/i).first()).toBeVisible();
    await expect(page.getByText(/TC-221|implementation/i).first()).toBeVisible();
  });
});
