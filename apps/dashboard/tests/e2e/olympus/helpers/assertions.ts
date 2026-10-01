import { expect, type Page } from "@playwright/test";
import { DELIVERY_CYCLES } from "../fixtures/journey-expectations";

export async function expectProjectContext(
  page: Page,
  opts: { project: string; deliveryCycle?: string; journey?: string },
) {
  await expect(page.getByTestId("project-context")).toHaveAttribute("data-key", opts.project);
  if (opts.deliveryCycle) {
    await expect(page.getByTestId("delivery-cycle-context")).toContainText(opts.deliveryCycle);
  }
  if (opts.journey) {
    await expect(page.getByTestId("journey-context")).toContainText(opts.journey.replace(/_/g, " "));
  }
}

export async function expectLifecycleStage(
  page: Page,
  opts: { active: string; state: string },
) {
  const stage = page.getByTestId(`lifecycle-stage-${opts.active}`);
  await expect(stage).toBeVisible();
  await expect(stage).toHaveAttribute("data-stage-state", opts.state);
}

export async function expectTaskState(page: Page, opts: { taskId: string; status: string }) {
  await expect(page.getByLabel(new RegExp(`Task ${opts.taskId} ${opts.status}`))).toBeVisible();
}

export async function expectShaOnPage(page: Page, fullSha: string) {
  await expect(page.locator(`[data-sha="${fullSha}"]`).first()).toBeVisible();
}

export async function expectFeatureChangeContext(page: Page) {
  await expectProjectContext(page, {
    project: "SUPPORTDESK",
    deliveryCycle: DELIVERY_CYCLES.featureChange,
    journey: "FEATURE_CHANGE",
  });
}
