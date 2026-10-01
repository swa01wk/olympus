import { expect, type Page } from "@playwright/test";
import { PROJECT_KEY } from "../fixtures/journey-expectations";

export class NavigationHelper {
  constructor(private readonly page: Page) {}

  async openProject(projectKey = PROJECT_KEY) {
    await this.page.goto("/projects");
    await this.page.getByRole("link", { name: new RegExp(projectKey, "i") }).first().click();
    await expect(this.page.getByRole("heading", { name: "Command Center" })).toBeVisible({
      timeout: 20_000,
    });
  }

  async navTo(label: string) {
    await this.page.getByRole("navigation", { name: "Project navigation" }).getByRole("link", { name: label }).click();
  }

  async selectCycle(cycleKey: string) {
    await this.page.getByRole("link", { name: cycleKey }).click();
  }
}
