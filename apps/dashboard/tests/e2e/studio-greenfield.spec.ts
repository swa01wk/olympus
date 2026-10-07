import { test, expect } from "@playwright/test";
import path from "node:path";
import {
  apiBaseUrl,
  apiReachable,
  approverToken,
  createGreenfieldCycle,
  createProject,
  liveStudioConfigured,
  operatorToken,
  applyTokenAndReload,
  setBrowserToken,
  waitForFeatures,
} from "./helpers/studio-live-api";

const prdPath = path.resolve(__dirname, "../../../../tests/fixtures/supportdesk/PRD.md");

test.describe("Studio greenfield @live", () => {
  test.beforeEach(async ({ request }, testInfo) => {
    if (!liveStudioConfigured()) {
      testInfo.skip(true, "Set OLYMPUS_OPERATOR_TOKEN and OLYMPUS_APPROVER_TOKEN");
      return;
    }
    if (!(await apiReachable(request))) {
      testInfo.skip(true, `Control API unreachable at ${apiBaseUrl()}`);
    }
  });

  test("DISCOVERY → scope approval → start_architecture + chat", { tag: "@live" }, async ({
    page,
    request,
  }) => {
    test.setTimeout(900_000);

    const operator = operatorToken()!;
    const approver = approverToken()!;

    const projectId = await createProject(request, operator);
    const cycleId = await createGreenfieldCycle(request, operator, projectId);

    await setBrowserToken(page, operator);
    await page.goto(`/projects/${projectId}/cycles/${cycleId}/studio`);

    await expect(page.getByRole("heading", { name: /Discovery/i })).toBeVisible({ timeout: 60_000 });

    const chatFileInput = page.locator(".ol-chat-composer input[type=file]");
    await page.getByRole("button", { name: "Attach PRD" }).click();
    await chatFileInput.setInputFiles(prdPath);
    await expect(page.getByText(/PRD v/i)).toBeVisible({ timeout: 120_000 });

    await page.getByRole("button", { name: "Decompose source" }).click();
    await page.getByRole("button", { name: "Confirm send" }).click();

    await waitForFeatures(request, operator, projectId, 1, 600_000);

    await page.getByRole("button", { name: /Product model/i }).click();
    await expect(page.getByText("Capabilities & features")).toBeVisible({ timeout: 30_000 });

    const featuresPanel = page.locator(".ol-ws-split").first();
    const featureBtn = featuresPanel.getByRole("button", { name: /^FEAT-/ }).first();
    await expect(featureBtn).toBeVisible({ timeout: 30_000 });
    await featureBtn.click();

    await page.getByRole("button", { name: "Edit spec" }).click();
    const summary = page.locator(".ol-ws-spec-form textarea").first();
    await summary.fill("Studio E2E updated summary for scope review.");
    await page.getByRole("button", { name: "Save new version" }).click();
    await expect(page.getByText(/Studio E2E updated summary/i)).toBeVisible({ timeout: 30_000 });

    await page.getByRole("button", { name: "Request scope approval" }).click();
    await page.getByRole("button", { name: "Confirm send" }).click();
    await expect(page.getByText(/Decision required/i)).toBeVisible({ timeout: 120_000 });

    await applyTokenAndReload(page, approver);
    await page.goto(`/projects/${projectId}/cycles/${cycleId}/studio?stage=PRODUCT_MODEL`);
    await expect(page.getByText(/Decision required/i)).toBeVisible({ timeout: 60_000 });

    const note = page.locator(".ol-decision-panel textarea, .ol-appr textarea").first();
    await note.fill("Please tighten acceptance criteria before scope sign-off.");
    await page.getByRole("button", { name: "Request changes" }).click();
    await expect(page.getByText(/Decision required/i)).toBeHidden({ timeout: 120_000 });

    await applyTokenAndReload(page, operator);
    await page.goto(`/projects/${projectId}/cycles/${cycleId}/studio?stage=PRODUCT_MODEL`);
    await page.getByRole("button", { name: "Request scope approval" }).click();
    await page.getByRole("button", { name: "Confirm send" }).click();
    await expect(page.getByText(/Decision required/i)).toBeVisible({ timeout: 120_000 });

    await applyTokenAndReload(page, approver);
    await page.goto(`/projects/${projectId}/cycles/${cycleId}/studio?stage=PRODUCT_MODEL`);
    await expect(page.getByText(/Decision required/i)).toBeVisible({ timeout: 60_000 });
    await page.getByRole("button", { name: "Approve" }).click();

    await applyTokenAndReload(page, operator);
    await page.goto(`/projects/${projectId}/cycles/${cycleId}/studio`);

    const advance = page.getByRole("button", { name: /start_architecture/i });
    await expect(advance).toBeVisible({ timeout: 120_000 });
    await expect(advance).toBeEnabled();

    const chatBox = page.locator(".ol-chat-composer textarea");
    await chatBox.fill("What is the next gate after product modeling?");
    await page.getByRole("button", { name: "Send" }).click();

    await expect(page.locator(".ol-chat-assistant .ol-body, .ol-chat-assistant p").first()).toBeVisible({
      timeout: 180_000,
    });
    await expect(page.getByText("Working…")).toHaveCount(0, { timeout: 180_000 });
  });
});
