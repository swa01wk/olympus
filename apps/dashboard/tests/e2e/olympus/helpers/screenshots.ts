import type { Page, TestInfo } from "@playwright/test";

export async function milestoneScreenshot(page: Page, testInfo: TestInfo, name: string) {
  const path = testInfo.outputPath(`milestones/${name}.png`);
  await page.screenshot({ path, fullPage: true });
  await testInfo.attach(name, { path, contentType: "image/png" });
}
