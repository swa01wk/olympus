import { defineConfig, devices } from "@playwright/test";

/** Prod server for E2E: CI or explicit E2E_PROD. Requires OLYMPUS_DEMO_BUILD=1 with fixture mode (see next.config.ts). */
const useProdServer = Boolean(process.env.CI || process.env.E2E_PROD);

export default defineConfig({
  testDir: "tests/e2e",
  fullyParallel: true,
  workers: process.env.CI ? 2 : 1,
  retries: process.env.CI ? 2 : 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  outputDir: "test-results/olympus",
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    testIdAttribute: "data-testid",
    viewport: { width: 1440, height: 900 },
  },
  projects: [
    {
      name: "frontend-e2e-fixture",
      grep: /@frontend-e2e/,
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: useProdServer ? "npm run build && npm run start" : "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    env: {
      NEXT_PUBLIC_OLYMPUS_DATA_MODE: "fixture",
      ...(useProdServer ? { OLYMPUS_DEMO_BUILD: "1" } : {}),
    },
  },
});
