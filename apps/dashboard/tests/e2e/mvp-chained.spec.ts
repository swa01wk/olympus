import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const repoRoot = path.resolve(__dirname, "../../../..");
const defaultPauseFile = path.join(repoRoot, "var/olympus/demo/pause.json");

function readPauseFile(): Record<string, unknown> | null {
  const pauseFile = process.env.MVP_PAUSE_FILE ?? defaultPauseFile;
  if (!fs.existsSync(pauseFile)) return null;
  return JSON.parse(fs.readFileSync(pauseFile, "utf-8")) as Record<string, unknown>;
}

function resumePauseFile(pause: Record<string, unknown>) {
  const pauseFile = process.env.MVP_PAUSE_FILE ?? defaultPauseFile;
  fs.writeFileSync(pauseFile, JSON.stringify({ ...pause, resumed: true }, null, 2));
}

test.describe("MVP chained operator walkthrough", () => {
  test("R3 release approval via ApprovalDialog (live stack)", async ({ page }) => {
    test.skip(!process.env.MVP_E2E_LIVE, "Set MVP_E2E_LIVE=1 with a running stack and pause file");

    const token = process.env.OLYMPUS_HUMAN_TOKEN;
    test.skip(!token, "OLYMPUS_HUMAN_TOKEN required for live walkthrough");

    const pauseRaw = readPauseFile();
    test.skip(!pauseRaw || pauseRaw.stage !== "approve_release:DC-004", "No active DC-004 release pause");
    const pause = pauseRaw as Record<string, unknown>;

    const approvalId = String(pause.approval_id ?? "");
    const projectId = String(pause.project_id ?? "");
    const cycleId = String(pause.cycle_id ?? "");
    test.skip(!approvalId || !projectId || !cycleId, "Pause file missing project/cycle/approval ids");

    await page.addInitScript((t) => {
      window.localStorage.setItem("olympus_api_token", t);
    }, token);

    const dashboardPath =
      typeof pause.dashboard_url === "string"
        ? new URL(pause.dashboard_url).pathname + new URL(pause.dashboard_url).search
        : `/projects/${projectId}/cycles/${cycleId}?approval=${approvalId}`;

    await page.goto(dashboardPath);

    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 60_000 });
    await page.getByPlaceholder(/Why you are approving/).fill("MVP chained walkthrough — R3 release approved.");
    await page.getByRole("button", { name: "Approve" }).click();
    await expect(page.getByRole("dialog")).toBeHidden({ timeout: 30_000 });

    resumePauseFile(pause);
  });
});
