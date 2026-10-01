import { test, expect } from "../fixtures/olympus.fixture";

test.describe("@frontend-e2e @fixture-journey navigation", () => {
  test("projects list renders SupportDesk", async ({ page, scenario }) => {
    await scenario.gotoCheckpoint("feature-change", "05-development-running");
    await expect(page.getByText(/SUPPORTDESK/i).first()).toBeVisible();
  });

  test("command center shows DC-003 development", async ({ page, scenario }) => {
    await scenario.gotoProjectCheckpoint("feature-change", "05-development-running", "DC-003");
    await expect(page.getByRole("link", { name: "DC-003" })).toBeVisible();
    await expect(page.getByText("DEVELOPMENT").first()).toBeVisible();
  });

  test("task DAG opens TASK-221", async ({ page, scenario }) => {
    await scenario.gotoProjectCheckpoint("feature-change", "05-development-running", "DC-003");
    await page.getByRole("navigation", { name: "Project navigation" }).getByRole("link", { name: "Tasks" }).click();
    await expect(page.getByRole("heading", { name: "Task DAG" })).toBeVisible();
    await expect(page.getByRole("button", { name: /TASK-221/ })).toBeVisible();
  });
});
