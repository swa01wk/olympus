import { test, expect } from "@playwright/test";
import projects from "../fixtures/projects.json";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("olympus_api_token", "playwright-test-token");
  });

  const api = process.env.NEXT_PUBLIC_OLYMPUS_API_URL ?? "http://127.0.0.1:8000";

  await page.route(`${api}/actors/me`, async (route) => {
    await route.fulfill({
      json: {
        actor_id: "22222222-2222-4222-8222-222222222222",
        kind: "human",
        name: "Playwright Operator",
        roles: ["operator"],
      },
    });
  });

  await page.route(`${api}/projects`, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ json: projects });
      return;
    }
    await route.continue();
  });
});

test("projects index lists fixture project", async ({ page }) => {
  await page.goto("/projects");
  await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
  await expect(page.getByRole("link", { name: /DEMO/ })).toBeVisible();
});
