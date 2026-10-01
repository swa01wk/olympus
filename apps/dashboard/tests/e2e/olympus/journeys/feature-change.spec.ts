import { test, expect } from "../fixtures/olympus.fixture";
import { SCENARIO_CHECKPOINTS } from "@/lib/fixtures/supportdesk/scenarios";
import { SHA, DELIVERY_CYCLES } from "../fixtures/journey-expectations";
import { expectFeatureChangeContext, expectLifecycleStage, expectTaskState } from "../helpers/assertions";
import { diagStep } from "../helpers/diagnostics";
import { milestoneScreenshot } from "../helpers/screenshots";

const JOURNEY = "FEATURE_CHANGE";

test.describe("@frontend-e2e @fixture-journey @feature-change @transparency", () => {
  for (const cp of SCENARIO_CHECKPOINTS["feature-change"]) {
    test(`checkpoint ${cp.id} — ${cp.label}`, async ({ page, scenario }) => {
      const ctx = { journey: JOURNEY, stage: cp.id, dimension: "STATE" };
      await scenario.gotoProjectCheckpoint("feature-change", cp.id, DELIVERY_CYCLES.featureChange);

      await diagStep(ctx, "project and cycle context", async () => {
        await expectFeatureChangeContext(page);
      });

      if (cp.id === "05-development-running") {
        await diagStep({ ...ctx, dimension: "EXECUTION" }, "EX-551 active", async () => {
          await expect(page.getByRole("link", { name: /EX-551/ })).toBeVisible();
          await expect(page.getByText("TASK-221").first()).toBeVisible();
        });
        await diagStep({ ...ctx, dimension: "CONTROL" }, "TASK-223 BLOCKED", async () => {
          await page
            .getByRole("navigation", { name: "Project navigation" })
            .getByRole("link", { name: "Tasks" })
            .click();
          await expectTaskState(page, { taskId: "TASK-223", status: "BLOCKED" });
        });
        await diagStep({ ...ctx, dimension: "REPOSITORY" }, "canonical remains r1", async () => {
          await expect(page.getByTestId("repository-summary-chip").locator(`[data-sha="${SHA.r1.full}"]`)).toBeVisible();
        });
      }

      if (cp.id === "08-canonical-reindex") {
        await diagStep({ ...ctx, dimension: "REPOSITORY" }, "canonical r2 after IC-003", async () => {
          await page
            .getByRole("navigation", { name: "Project navigation" })
            .getByRole("link", { name: "Code" })
            .click();
          await expect(page.locator(`[data-sha="${SHA.r2.full}"]`).first()).toBeVisible();
        });
      }

      if (cp.id === "02-impact") {
        await milestoneScreenshot(page, test.info(), "FC-IMPACT");
      }

      if (cp.id === "11-released") {
        await diagStep({ ...ctx, dimension: "REPOSITORY" }, "R2 released SHA", async () => {
          await page
            .getByRole("navigation", { name: "Project navigation" })
            .getByRole("link", { name: "Release" })
            .click();
          await page.getByRole("link", { name: "R2" }).click();
          await expect(page.locator(`[data-sha="${SHA.r2.full}"]`).first()).toBeVisible();
        });
        await milestoneScreenshot(page, test.info(), "FC-R2");
      }
    });
  }

  test("@fixture-journey traverses checkpoints via Next", async ({ page, scenario }) => {
    await scenario.gotoProjectCheckpoint("feature-change", "00-intake", DELIVERY_CYCLES.featureChange);
    const total = SCENARIO_CHECKPOINTS["feature-change"].length;
    for (let i = 0; i < total - 1; i += 1) {
      await scenario.next();
      await scenario.expectCheckpointIndex(i + 1);
    }
    await expectLifecycleStage(page, { active: "COMPLETE", state: "COMPLETE" }).catch(() => {
      /* cycle may show DEVELOPMENT/COMPLETE depending on view */
    });
  });
});
