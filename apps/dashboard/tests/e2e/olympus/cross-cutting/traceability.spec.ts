import { test, expect } from "../fixtures/olympus.fixture";
import { DELIVERY_CYCLES } from "../fixtures/journey-expectations";

test.describe("@frontend-e2e @transparency @lineage", () => {
  test("lineage page loads with query params", async ({ page, scenario }) => {
    await scenario.gotoProjectCheckpoint("feature-change", "11-released", DELIVERY_CYCLES.featureChange);
    const m = page.url().match(/\/projects\/([^/?]+)/);
    const projectId = m?.[1] ?? "";
    await page.goto(
      `/projects/${projectId}/lineage?root_type=METHOD&root_id=00000000-0000-4000-8000-000000000001&direction=REVERSE`,
    );
    await expect(page.getByText(/REVERSE|nodes/i).first()).toBeVisible();
  });
});
