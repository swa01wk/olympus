import { test, expect } from "../fixtures/olympus.fixture";
import { SCENARIO_CHECKPOINTS } from "@/lib/fixtures/supportdesk/scenarios";
import { DELIVERY_CYCLES, SHA } from "../fixtures/journey-expectations";
import { expectProjectContext } from "../helpers/assertions";
import { milestoneScreenshot } from "../helpers/screenshots";

test.describe("@frontend-e2e @fixture-journey @bug-fix", () => {
  test("00-defect-intake DEF-004", async ({ page, scenario }) => {
    await scenario.gotoProjectCheckpoint("bug-fix", "00-defect-intake", DELIVERY_CYCLES.bugFix);
    await expectProjectContext(page, {
      project: "SUPPORTDESK",
      deliveryCycle: DELIVERY_CYCLES.bugFix,
      journey: "BUG_FIX",
    });
    await expect(page.getByText("DEF-004")).toBeVisible();
  });

  test("07-assurance-fail release blocked", async ({ page, scenario }) => {
    await scenario.gotoProjectCheckpoint("bug-fix", "07-assurance-fail", DELIVERY_CYCLES.bugFix);
    await expect(page.getByText(/NOT_ELIGIBLE|RELEASE BLOCKED|blocked/i).first()).toBeVisible();
    await milestoneScreenshot(page, test.info(), "BUG-ASSURANCE-FAIL");
  });

  test("11-released R3", async ({ page, scenario }) => {
    await scenario.gotoProjectCheckpoint("bug-fix", "11-released", DELIVERY_CYCLES.bugFix);
    await page.getByRole("navigation", { name: "Project navigation" }).getByRole("link", { name: "Release" }).click();
    await page.getByRole("link", { name: "R3" }).click();
    await expect(page.locator(`[data-sha="${SHA.r3.full}"]`).first()).toBeVisible();
    await milestoneScreenshot(page, test.info(), "BUG-R3");
  });

  test("traverses checkpoints", async ({ scenario }) => {
    await scenario.gotoCheckpoint("bug-fix", "00-defect-intake");
    for (let i = 0; i < SCENARIO_CHECKPOINTS["bug-fix"].length - 1; i += 1) {
      await scenario.next();
    }
    await scenario.expectPosition("bug-fix", "11-released");
  });
});
