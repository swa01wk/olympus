import { test, expect } from "../fixtures/olympus.fixture";
import { formatFxParam } from "@/lib/api/fx-param";
import { PROJECT_ID } from "../fixtures/journey-expectations";

test.describe("@frontend-e2e @fixture-journey scenario controls", () => {
  test("next, jump, reset and fx param persist", async ({ page, scenario }) => {
    await scenario.gotoCheckpoint("feature-change", "00-intake", `/projects/${PROJECT_ID}`);
    await scenario.next();
    await expect.poll(async () => scenario.bar().getAttribute("data-checkpoint-id")).toBe("01-spec-delta");
    await scenario.gotoCheckpoint("feature-change", "05-development-running", `/projects/${PROJECT_ID}`);
    await scenario.gotoCheckpoint("feature-change", "00-intake", `/projects/${PROJECT_ID}`);
    expect(page.url()).toContain(formatFxParam("feature-change", "00-intake"));
  });

  test("scenario switch changes runtime attribute", async ({ scenario }) => {
    await scenario.gotoCheckpoint("greenfield", "00-intake", `/projects/${PROJECT_ID}`);
    await expect(scenario.bar()).toHaveAttribute("data-runtime", "A");
    await scenario.gotoCheckpoint("brownfield", "00-registration", `/projects/${PROJECT_ID}`);
    await expect(scenario.bar()).toHaveAttribute("data-runtime", "B");
    await expect(scenario.bar()).toHaveAttribute("data-checkpoint-id", "00-registration");
  });
});
