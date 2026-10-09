import { test, expect } from "@playwright/test";
import path from "node:path";
import {
  apiReachable,
  approverToken,
  bootstrapGreenfieldToArchitecture,
  createGreenfieldCycle,
  createProject,
  liveStudioConfigured,
  operatorToken,
  applyTokenAndReload,
  waitForArchitectureVersion,
} from "./helpers/studio-live-api";

const prdPath = path.resolve(__dirname, "../../../../tests/fixtures/supportdesk/PRD.md");

const REVISION_NOTE =
  "Put the archived-project rule in one ProjectGuard used by the service layer";

test.describe("Studio RL2 phase acceptance @live", () => {
  test.beforeEach(async ({ request }, testInfo) => {
    if (!liveStudioConfigured()) {
      testInfo.skip(true, "Set OLYMPUS_OPERATOR_TOKEN and OLYMPUS_APPROVER_TOKEN");
      return;
    }
    if (!(await apiReachable(request))) {
      testInfo.skip(true, "Control API unreachable");
    }
  });

  test("architecture chat propose, cite, request-changes revision", { tag: "@live" }, async ({
    page,
    request,
  }) => {
    test.setTimeout(1_800_000);

    const operator = operatorToken()!;
    const approver = approverToken()!;

    const projectId = await createProject(request, operator);
    const cycleId = await createGreenfieldCycle(request, operator, projectId);

    await bootstrapGreenfieldToArchitecture(page, request, {
      operator,
      approver,
      projectId,
      cycleId,
      prdPath,
    });

    const chatBox = page.locator(".ol-chat-composer textarea");
    await chatBox.fill("We need an architecture for this cycle. Please propose generating it.");
    await page.getByRole("button", { name: "Send" }).click();

    const proposal = page.locator(".ol-chat-proposal").filter({ hasText: "architecture.propose" });
    await expect(proposal).toBeVisible({ timeout: 240_000 });
    await proposal.getByRole("button", { name: "Run" }).click();
    await expect(proposal.getByText(/Command completed/i)).toBeVisible({ timeout: 120_000 });

    await waitForArchitectureVersion(request, operator, projectId, 1, 900_000);
    await page.reload();
    await expect(page.getByText(/Architecture/i).first()).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(/^v1 · /i)).toBeVisible({ timeout: 60_000 });

    await expect(page.getByText(/Decision required/i)).toBeVisible({ timeout: 120_000 });

    await chatBox.fill(
      "Why is archived or closed project access handled the way it is in this architecture?",
    );
    await page.getByRole("button", { name: "Send" }).click();
    const assistant = page.locator(".ol-chat-assistant").last();
    await expect(assistant).toBeVisible({ timeout: 240_000 });
    await expect(assistant).toContainText(/archiv|guard|decision|409|project/i, { timeout: 60_000 });

    await applyTokenAndReload(page, approver);
    await page.goto(`/projects/${projectId}/cycles/${cycleId}/studio?stage=ARCHITECTURE`);
    await expect(page.getByText(/Decision required/i)).toBeVisible({ timeout: 120_000 });

    const note = page.locator(".ol-decision-panel textarea");
    await note.fill(REVISION_NOTE);
    await page.getByRole("button", { name: "Request changes" }).click();

    await expect(page.getByText(/Revising:/i)).toBeVisible({ timeout: 120_000 });
    await expect(page.getByText(/Revising:/i)).toBeHidden({ timeout: 900_000 });

    await waitForArchitectureVersion(request, operator, projectId, 2, 900_000);
    await page.reload();
    await expect(page.getByText(/^v2 · /i)).toBeVisible({ timeout: 120_000 });
    await expect(page.locator(".ol-revision-diff, .ol-ws-pre").first()).toBeVisible({
      timeout: 120_000,
    });

    await applyTokenAndReload(page, approver);
    await page.goto(`/projects/${projectId}/cycles/${cycleId}/studio?stage=ARCHITECTURE`);
    await expect(page.getByText(/Decision required/i)).toBeVisible({ timeout: 180_000 });

    await applyTokenAndReload(page, operator);
    await page.goto(`/projects/${projectId}/cycles/${cycleId}/studio`);
    await page.getByRole("button", { name: "Product spec" }).click();
    await expect(page.getByRole("heading", { name: /Product spec/i })).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.locator(".ol-product-spec")).toBeVisible();
  });
});
