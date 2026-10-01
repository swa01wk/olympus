import { test } from "../fixtures/olympus.fixture";
import { expectProjectContext } from "../helpers/assertions";
import { DELIVERY_CYCLES } from "../fixtures/journey-expectations";

test.describe("@frontend-e2e @transparency @state", () => {
  test("feature-change development shows cycle and journey", async ({ page, scenario }) => {
    await scenario.gotoProjectCheckpoint("feature-change", "05-development-running", DELIVERY_CYCLES.featureChange);
    await expectProjectContext(page, {
      project: "SUPPORTDESK",
      deliveryCycle: DELIVERY_CYCLES.featureChange,
      journey: "FEATURE_CHANGE",
    });
  });
});
