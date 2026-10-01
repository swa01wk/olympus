import { test as base } from "@playwright/test";
import { ScenarioHelper } from "../helpers/scenario";
import { NavigationHelper } from "../helpers/navigation";

type OlympusFixtures = {
  scenario: ScenarioHelper;
  nav: NavigationHelper;
};

export const test = base.extend<OlympusFixtures>({
  scenario: async ({ page }, use) => {
    await use(new ScenarioHelper(page));
  },
  nav: async ({ page }, use) => {
    await use(new NavigationHelper(page));
  },
});

export { expect } from "@playwright/test";
