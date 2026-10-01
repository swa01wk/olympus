import { test, expect } from "../fixtures/olympus.fixture";
import { DELIVERY_CYCLES, SHA } from "../fixtures/journey-expectations";

test.describe("@frontend-e2e @fixture-journey cross-journey", () => {
  test("release history R1 R2 R3 at bug-fix final", async ({ page, scenario }) => {
    await scenario.gotoProjectCheckpoint("bug-fix", "11-released", DELIVERY_CYCLES.bugFix);
    await page.getByRole("navigation", { name: "Project navigation" }).getByRole("link", { name: "Release" }).click();
    await expect(page.getByRole("heading", { name: "Releases" })).toBeVisible();
    const list = page.locator("ul").first();
    await expect(list).toContainText("R1");
    await expect(list).toContainText("R2");
    await expect(list).toContainText("R3");
  });

  test("canonical SHA progression on repository at R3", async ({ page, scenario }) => {
    await scenario.gotoProjectCheckpoint("bug-fix", "11-released", "DC-004");
    await expect(page.getByTestId("repository-summary-chip")).toContainText(SHA.r3.label);
  });
});
