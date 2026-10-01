import { expect, type Page } from "@playwright/test";

export async function expectRepositoryTruth(
  page: Page,
  opts: { canonicalSha: string; codeIndex?: string },
) {
  const chip = page.getByTestId("repository-summary-chip");
  await expect(chip).toBeVisible();
  await expect(page.locator(`[data-sha="${opts.canonicalSha}"]`).first()).toBeVisible();
  if (opts.codeIndex) {
    await expect(page.getByText(opts.codeIndex)).toBeVisible();
  }
}
