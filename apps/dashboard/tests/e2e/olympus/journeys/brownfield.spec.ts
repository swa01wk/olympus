import { test, expect } from "../fixtures/olympus.fixture";
import { SCENARIO_CHECKPOINTS } from "@/lib/fixtures/supportdesk/scenarios";
import { DELIVERY_CYCLES } from "../fixtures/journey-expectations";
import { expectProjectContext } from "../helpers/assertions";
import { milestoneScreenshot } from "../helpers/screenshots";

test.describe("@frontend-e2e @fixture-journey @brownfield", () => {
  test("00-registration external clone", async ({ page, scenario }) => {
    await scenario.gotoProjectCheckpoint("brownfield", "00-registration", DELIVERY_CYCLES.brownfield);
    await expectProjectContext(page, {
      project: "SUPPORTDESK",
      deliveryCycle: DELIVERY_CYCLES.brownfield,
      journey: "BROWNFIELD_ONBOARDING",
    });
    await expect(page.getByText(/GITHUB|EXTERNAL/i).first()).toBeVisible();
  });

  test("11-ready-for-change", async ({ page, scenario }) => {
    await scenario.gotoProjectCheckpoint("brownfield", "11-ready-for-change", DELIVERY_CYCLES.brownfield);
    await expect(page.getByTestId("project-context")).toContainText("SUPPORTDESK");
    await expect(page.getByTestId("delivery-cycle-context")).toContainText("DC-002");
    await milestoneScreenshot(page, test.info(), "BF-READY");
  });

  test("traverses checkpoints", async ({ scenario }) => {
    await scenario.gotoCheckpoint("brownfield", "00-registration");
    for (let i = 0; i < SCENARIO_CHECKPOINTS.brownfield.length - 1; i += 1) {
      await scenario.next();
    }
    await scenario.expectPosition("brownfield", "11-ready-for-change");
  });
});
