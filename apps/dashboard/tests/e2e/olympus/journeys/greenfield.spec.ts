import { test, expect } from "../fixtures/olympus.fixture";
import { SCENARIO_CHECKPOINTS } from "@/lib/fixtures/supportdesk/scenarios";
import { DELIVERY_CYCLES, SHA } from "../fixtures/journey-expectations";
import { expectProjectContext } from "../helpers/assertions";
import { milestoneScreenshot } from "../helpers/screenshots";

test.describe("@frontend-e2e @fixture-journey @greenfield", () => {
  test("checkpoint 00-intake initial state", async ({ page, scenario }) => {
    await scenario.gotoProjectCheckpoint("greenfield", "00-intake", DELIVERY_CYCLES.greenfield);
    await expectProjectContext(page, {
      project: "SUPPORTDESK",
      deliveryCycle: DELIVERY_CYCLES.greenfield,
      journey: "GREENFIELD_BUILD",
    });
    await expect(page.getByRole("heading", { name: "Command Center" })).toBeVisible();
  });

  test("checkpoint 14-released R1", async ({ page, scenario }) => {
    await scenario.gotoProjectCheckpoint("greenfield", "14-released", DELIVERY_CYCLES.greenfield);
    await expect(page.getByTestId("repository-summary-chip")).toContainText(SHA.r1.label);
    await milestoneScreenshot(page, test.info(), "GF-R1");
  });

  test("traverses all checkpoints", async ({ scenario }) => {
    await scenario.gotoCheckpoint("greenfield", "00-intake");
    const total = SCENARIO_CHECKPOINTS.greenfield.length;
    for (let i = 0; i < total - 1; i += 1) {
      await scenario.next();
    }
    await scenario.expectPosition("greenfield", "14-released");
  });
});
