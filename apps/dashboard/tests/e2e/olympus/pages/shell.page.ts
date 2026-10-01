import type { Page } from "@playwright/test";

export class ShellPage {
  constructor(readonly page: Page) {}

  scenarioBar() {
    return this.page.getByTestId("scenario-control-bar");
  }

  projectContext() {
    return this.page.getByTestId("project-context");
  }

  cycleContext() {
    return this.page.getByTestId("delivery-cycle-context");
  }
}
