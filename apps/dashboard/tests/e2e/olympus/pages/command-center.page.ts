import type { Page } from "@playwright/test";

export class CommandCenterPage {
  constructor(readonly page: Page) {}

  heading() {
    return this.page.getByRole("heading", { name: "Command Center" });
  }

  activeExecution(key: string) {
    return this.page.getByText(key);
  }
}
