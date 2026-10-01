import { test, expect } from "../fixtures/olympus.fixture";
import { DELIVERY_CYCLES } from "../fixtures/journey-expectations";

test.describe("@frontend-e2e @transparency @control-plane", () => {
  test("TASK-223 blocked reason on control plane", async ({ page, scenario }) => {
    await scenario.gotoProjectCheckpoint("feature-change", "05-development-running", DELIVERY_CYCLES.featureChange);
    await page.getByRole("navigation", { name: "Project navigation" }).getByRole("link", { name: "Control Plane" }).click();
    await expect(page.getByRole("heading", { name: "Control Plane Inspector" })).toBeVisible();
    await expect(page.getByText(/TASK-223/).first()).toBeVisible();
    await expect(page.getByText(/TASK-222|DEPENDENCY_INCOMPLETE/i).first()).toBeVisible();
  });
});
