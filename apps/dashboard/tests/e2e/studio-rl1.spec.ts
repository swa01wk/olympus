import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import {
  apiBaseUrl,
  apiReachable,
  approverToken,
  applyTokenAndReload,
  liveStudioConfigured,
  operatorToken,
  setBrowserToken,
} from "./helpers/studio-live-api";

/**
 * RL1 phase acceptance: brownfield intake → review queue → READY, then a feature change up to the
 * architecture-delta panel and a bug fix up to the repair-spec Decision panel, driven from the
 * Studio. The repository must be staged as a bare repo inside the shared Docker volume (see
 * STUDIO_RL1_REPO_URL); setup and polling use the API, every RL1 action uses the UI.
 */
const REPO_URL =
  process.env.STUDIO_RL1_REPO_URL ?? "file:///data/workspaces/fixtures/supportdesk.git";

const CHANGE_TITLE = "Ticket priority";
const CHANGE_DESCRIPTION =
  "Add ticket priority: LOW, MEDIUM, HIGH. Existing tickets default to MEDIUM when priority is " +
  "not specified. Priority changes must be pushed to the external paging integration, so add an " +
  "integration component that notifies on HIGH priority tickets.";

const DEFECT_TITLE = "Updating a CLOSED ticket returns HTTP 500";
const DEFECT_DESCRIPTION =
  "When PATCHing a ticket that is already CLOSED, the API returns HTTP 500 instead of rejecting " +
  "the update. Expected behavior is HTTP 409 Conflict per product acceptance criteria.";

type Ctx = { projectId: string; brownfieldCycleId?: string };
const ctx: Ctx = { projectId: "" };

function headers(token: string, idem?: string): Record<string, string> {
  const h: Record<string, string> = { Authorization: `Bearer ${token}`, Accept: "application/json" };
  if (idem) h["Idempotency-Key"] = idem;
  return h;
}

async function apiGet<T>(request: APIRequestContext, token: string, path: string): Promise<T | null> {
  try {
    const res = await request.get(`${apiBaseUrl()}${path}`, { headers: headers(token), timeout: 60_000 });
    return res.ok() ? ((await res.json()) as T) : null;
  } catch {
    return null;
  }
}

async function poll<T>(
  label: string,
  timeoutMs: number,
  probe: () => Promise<T | null | undefined | false>,
  intervalMs = 5_000,
): Promise<T> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const v = await probe();
    if (v) return v;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error(`Timed out: ${label}`);
}

type Transition = {
  command: string;
  allowed: boolean;
  authorization_denied?: boolean;
  guard_results?: { guard_id: string; ok: boolean; reasons: string[] }[];
};

async function cycleState(request: APIRequestContext, token: string, cycleId: string) {
  const c = await apiGet<{ state: string }>(request, token, `/delivery-cycles/${cycleId}`);
  return c?.state ?? "";
}

async function transitions(request: APIRequestContext, token: string, cycleId: string) {
  return (await apiGet<Transition[]>(request, token, `/delivery-cycles/${cycleId}/next-transitions`)) ?? [];
}

async function cycleTasks(request: APIRequestContext, token: string, cycleId: string) {
  return (
    (await apiGet<{ key: string; title: string; status: string; blocked_reason: string | null }[]>(
      request,
      token,
      `/delivery-cycles/${cycleId}/tasks`,
    )) ?? []
  );
}

async function failIfTaskFailed(request: APIRequestContext, token: string, cycleId: string) {
  const failed = (await cycleTasks(request, token, cycleId)).filter((t) => t.status === "FAILED");
  if (failed.length > 0) throw new Error(`Agent task failed: ${JSON.stringify(failed)}`);
}

async function openStudio(page: Page, projectId: string, cycleId: string, stage?: string) {
  const q = stage ? `?stage=${stage}` : "";
  await page.goto(`/projects/${projectId}/cycles/${cycleId}/studio${q}`);
  await expect(page.getByRole("list", { name: "Delivery stages" })).toBeVisible({ timeout: 90_000 });
}

/**
 * Wait until next-transitions allows `command`, then run it from the Studio Next step bar.
 * `sameState` commands (retries) keep the cycle state; they are done once the command closes.
 */
async function advance(
  page: Page,
  request: APIRequestContext,
  token: string,
  projectId: string,
  cycleId: string,
  command: string,
  timeoutMs: number,
  { sameState = false }: { sameState?: boolean } = {},
) {
  const before = await cycleState(request, token, cycleId);
  const last: { t?: Transition } = {};
  await poll(`${command} allowed (cycle ${cycleId})`, timeoutMs, async () => {
    await failIfTaskFailed(request, token, cycleId);
    last.t = (await transitions(request, token, cycleId)).find((t) => t.command === command);
    return last.t?.allowed && !last.t.authorization_denied;
  }).catch((e: Error) => {
    throw new Error(`${e.message}; last preview=${JSON.stringify(last.t)}`);
  });

  await openStudio(page, projectId, cycleId);
  const bar = page.locator(".ol-next-step-bar");
  const primary = bar.getByRole("button", { name: new RegExp(`^${command} →`) });
  await primary.waitFor({ state: "visible", timeout: 30_000 }).catch(() => undefined);
  if (!(await primary.isVisible())) {
    await bar.getByRole("button", { name: "More commands" }).click();
    await bar.getByRole("button", { name: new RegExp(`^${command}`) }).click();
  } else {
    await expect(primary).toBeEnabled({ timeout: 60_000 });
    await primary.click();
  }
  await expect(bar.locator(".ol-cmd-api")).toContainText(`/commands/${command}`);
  await bar.getByRole("button", { name: `Confirm ${command}` }).click();
  if (sameState) {
    await poll(`${command} applied`, 120_000, async () => {
      const t = (await transitions(request, token, cycleId)).find((x) => x.command === command);
      return !t?.allowed;
    }, 2_000);
    return;
  }
  await poll(`state change after ${command}`, 120_000, async () => {
    const s = await cycleState(request, token, cycleId);
    return s && s !== before;
  }, 2_000);
}

const BUG_FIX_ORDER = ["TRIAGE", "REPRODUCTION", "EXPECTED_BEHAVIOR", "ROOT_CAUSE"];

/**
 * Bug-fix stages advance on their own when the previous agent output qualifies (triage → reproduce,
 * reproduced → expected behavior → root cause). Run `command` from the Studio only if the backend
 * offers it before the cycle reaches `target` by itself.
 */
async function reachBugFixStage(
  page: Page,
  request: APIRequestContext,
  token: string,
  projectId: string,
  cycleId: string,
  command: string,
  target: string,
  timeoutMs: number,
) {
  const reached = (s: string) => BUG_FIX_ORDER.indexOf(s) >= BUG_FIX_ORDER.indexOf(target);
  const how = await poll(`${target} reached or ${command} allowed (cycle ${cycleId})`, timeoutMs, async () => {
    await failIfTaskFailed(request, token, cycleId);
    const state = await cycleState(request, token, cycleId);
    if (reached(state)) return "auto" as const;
    const ts = await transitions(request, token, cycleId);
    const t = ts.find((x) => x.command === command);
    if (t?.allowed && !t.authorization_denied) return "manual" as const;
    const notReproduced = ts.some((x) =>
      x.guard_results?.some((g) => g.reasons.includes("NOT_REPRODUCED")),
    );
    const active = (await cycleTasks(request, token, cycleId)).some((x) =>
      ["READY", "QUEUED", "RUNNING"].includes(x.status),
    );
    if (state === "REPRODUCTION" && notReproduced && !active) {
      throw new Error(`reproduction finished NOT_REPRODUCED (cycle ${cycleId})`);
    }
    return false;
  });
  if (how === "manual") await advance(page, request, token, projectId, cycleId, command, 120_000);
  await poll(`${target} reached (cycle ${cycleId})`, timeoutMs, async () => {
    await failIfTaskFailed(request, token, cycleId);
    return reached(await cycleState(request, token, cycleId));
  });
}

async function pendingApproval(
  request: APIRequestContext,
  token: string,
  cycleId: string,
  approvalType: string,
) {
  const inbox =
    (await apiGet<{ kind: string; approval?: { id: string; approval_type: string; status: string } }[]>(
      request,
      token,
      `/views/inbox?delivery_cycle_id=${cycleId}`,
    )) ?? [];
  return inbox.find(
    (i) => i.approval?.approval_type === approvalType && i.approval.status === "PENDING",
  )?.approval;
}

async function approveInDecisionPanel(page: Page, approvalType: string) {
  const panel = page.locator(".ol-decision-panel");
  await expect(panel).toBeVisible({ timeout: 120_000 });
  await expect(panel).toContainText(approvalType);
  await panel.getByRole("button", { name: "Approve" }).click();
  await expect(panel).toBeHidden({ timeout: 120_000 });
}

type QueueItem = { subject_type: string; subject_id: string; decided: boolean };

const FIRST_CHOICE: Record<string, string> = {
  ARCHITECTURE: "APPROVE_AS_PROJECT_ARCHITECTURE",
  FEATURE_SPEC: "PROMOTE_AS_CANONICAL",
  IMPLEMENTATION_SPEC: "PROMOTE_AS_CANONICAL",
  BASELINE: "ACTIVATE",
  UNCERTAINTY: "ACCEPT_KNOWN_GAP",
};
const FALLBACK: Record<string, string> = {
  FEATURE_SPEC: "CONFIRM_EXISTING",
  IMPLEMENTATION_SPEC: "REJECT_AS_NOT_INTENDED",
  BASELINE: "REJECT_AS_NOT_INTENDED",
};

async function decideInReviewQueue(page: Page, item: QueueItem, decision: string): Promise<boolean> {
  const row = page.locator("li.ol-ws-row").filter({ hasText: item.subject_id });
  await expect(row).toBeVisible({ timeout: 60_000 });
  await row.getByRole("radio", { name: decision.replace(/_/g, " "), exact: true }).check();
  const note = row.locator("textarea");
  if (await note.isEnabled()) await note.fill(`RL1 live review: ${decision.toLowerCase()}`);
  await row.getByRole("button", { name: "Preview decision" }).click();
  await expect(row.locator(".ol-cmd-api")).toContainText("promotion-decisions");
  await row.getByRole("button", { name: "Confirm send" }).click();
  const outcome = await Promise.race([
    row.waitFor({ state: "detached", timeout: 60_000 }).then(() => "ok" as const),
    row.getByRole("alert").waitFor({ timeout: 60_000 }).then(() => "error" as const),
  ]);
  return outcome === "ok";
}

test.describe.serial("Studio RL1 phase acceptance @live", () => {
  test.beforeEach(async ({ request }, testInfo) => {
    if (!liveStudioConfigured()) {
      testInfo.skip(true, "Set OLYMPUS_OPERATOR_TOKEN and OLYMPUS_APPROVER_TOKEN");
      return;
    }
    if (!(await apiReachable(request))) testInfo.skip(true, "Control API unreachable");
  });

  test("brownfield: register → READY → cycle → review queue → READY_FOR_CHANGE", { tag: "@live" }, async ({
    page,
    request,
  }) => {
    test.setTimeout(3_600_000);
    const operator = operatorToken()!;
    const approver = approverToken()!;

    const key = `RL${Date.now().toString(36).toUpperCase().slice(-6)}`;
    const projRes = await request.post(`${apiBaseUrl()}/projects`, {
      headers: headers(operator, randomUUID()),
      data: { key, name: `RL1 live ${key}` },
    });
    expect(projRes.ok(), await projRes.text()).toBeTruthy();
    ctx.projectId = ((await projRes.json()) as { id: string }).id;
    const projectId = ctx.projectId;

    await setBrowserToken(page, operator);
    await page.goto(`/projects/${projectId}`);
    await page.getByRole("button", { name: "New delivery cycle" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("radio", { name: "Brownfield Onboarding" }).click();
    await dialog.getByRole("radio", { name: "Register new" }).click();
    const field = (label: string) =>
      dialog.locator("label.ol-field").filter({ hasText: label }).locator("input, select, textarea");
    await field("Name").fill("supportdesk");
    await field("Provider").selectOption("LOCAL");
    await field("Remote URL").fill(REPO_URL);
    await field("Default branch").fill("main");
    await dialog.getByRole("button", { name: "Register repository" }).click();
    await expect(dialog.locator(".ol-cmd-api").filter({ hasText: "/repositories" }).first()).toBeVisible();
    await dialog.getByRole("button", { name: "Confirm send" }).click();

    const materialization = dialog.getByRole("status").filter({ hasText: "Materialization" });
    await expect(materialization).toContainText(/READY|ERROR/, { timeout: 300_000 });
    await expect(materialization).not.toContainText("ERROR");

    await field("Objective").fill("Onboard the existing SupportDesk service");
    await dialog.getByRole("button", { name: "Create delivery cycle" }).click();
    await page.waitForURL(/\/cycles\/[^/]+\/studio/, { timeout: 60_000 });
    const cycleId = page.url().match(/cycles\/([^/]+)\/studio/)![1]!;
    ctx.brownfieldCycleId = cycleId;
    await expect(page.getByRole("heading", { name: "RECON", level: 1 })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(REPO_URL).first()).toBeVisible();
    await expect(page.getByText("Canonical commit").first()).toBeVisible();

    await advance(page, request, operator, projectId, cycleId, "start_code_index", 300_000);
    await advance(page, request, operator, projectId, cycleId, "start_spec_recovery", 600_000);
    const proposals = async () =>
      (
        await apiGet<{ proposals: { status: string; validation_report?: unknown }[] }>(
          request,
          operator,
          `/delivery-cycles/${cycleId}/recovery`,
        )
      )?.proposals ?? [];
    for (let attempt = 1; ; attempt += 1) {
      const seen = attempt - 1;
      const rows = await poll(`recovery proposal (attempt ${attempt})`, 2_400_000, async () => {
        await failIfTaskFailed(request, operator, cycleId);
        const r = await proposals();
        return r.length > seen ? r : false;
      });
      const latest = rows[0]!;
      if (latest.status === "VALIDATED") break;
      if (attempt >= 3) {
        throw new Error(`recovery proposal REJECTED ${attempt} times: ${JSON.stringify(latest.validation_report)}`);
      }
      await advance(page, request, operator, projectId, cycleId, "retry_spec_recovery", 120_000, {
        sameState: true,
      });
    }
    await advance(page, request, operator, projectId, cycleId, "start_baseline", 300_000);

    await poll("baseline agents idle", 1_800_000, async () => {
      await failIfTaskFailed(request, operator, cycleId);
      const tasks = await cycleTasks(request, operator, cycleId);
      return !tasks.some((t) => ["READY", "QUEUED", "RUNNING"].includes(t.status));
    });

    await applyTokenAndReload(page, approver);
    await openStudio(page, projectId, cycleId, "BASELINE");
    await expect(page.getByRole("heading", { name: /Review queue/i }).or(page.getByText("Review queue").first())).toBeVisible({ timeout: 60_000 });

    for (let round = 0; round < 80; round += 1) {
      const queue =
        (await apiGet<QueueItem[]>(request, approver, `/delivery-cycles/${cycleId}/review-queue`)) ?? [];
      const next = queue.find((i) => !i.decided);
      if (!next) break;
      await page.reload();
      const first = FIRST_CHOICE[next.subject_type] ?? "DEFER";
      let ok = await decideInReviewQueue(page, next, first);
      if (!ok && FALLBACK[next.subject_type]) {
        await page.reload();
        ok = await decideInReviewQueue(page, next, FALLBACK[next.subject_type]!);
      }
      expect(ok, `decision failed for ${next.subject_type} ${next.subject_id}`).toBeTruthy();
    }

    await applyTokenAndReload(page, operator);
    await advance(page, request, operator, projectId, cycleId, "start_readiness", 600_000);
    const readiness = await poll("readiness assessed", 300_000, () =>
      apiGet<{ result: string; remediable: boolean; reasons: unknown }>(
        request,
        operator,
        `/delivery-cycles/${cycleId}/readiness`,
      ),
    );
    expect(readiness.result, `readiness: ${JSON.stringify(readiness)}`).toBe("READY");
    await advance(page, request, operator, projectId, cycleId, "declare_ready", 120_000);
    await poll("project READY_FOR_CHANGE", 60_000, async () => {
      const p = await apiGet<{ readiness_state: string }>(request, operator, `/projects/${projectId}`);
      return p?.readiness_state === "READY_FOR_CHANGE";
    });
  });

  test("feature change: architecture-delta panel at IMPACT_ANALYSIS", { tag: "@live" }, async ({
    page,
    request,
  }) => {
    test.setTimeout(2_400_000);
    test.skip(!ctx.projectId, "brownfield onboarding did not run");
    const operator = operatorToken()!;
    const approver = approverToken()!;
    const { projectId } = ctx;

    await setBrowserToken(page, operator);
    await page.goto(`/projects/${projectId}`);
    await page.getByRole("button", { name: "New delivery cycle" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("radio", { name: "Feature Change" }).click();
    await dialog.locator("label.ol-field").filter({ hasText: "Change request title" }).locator("input").fill(CHANGE_TITLE);
    await dialog.locator("label.ol-field").filter({ hasText: "Description" }).locator("textarea").fill(CHANGE_DESCRIPTION);
    await expect(dialog.locator(".ol-cmd-api").last()).toContainText("/change-requests");
    await dialog.getByRole("button", { name: "Create delivery cycle" }).click();
    await page.waitForURL(/\/cycles\/[^/]+\/studio/, { timeout: 60_000 });
    const cycleId = page.url().match(/cycles\/([^/]+)\/studio/)![1]!;

    await advance(page, request, operator, projectId, cycleId, "start_spec_delta", 120_000);
    await poll("SPEC_DELTA approval pending", 1_200_000, async () => {
      await failIfTaskFailed(request, operator, cycleId);
      return pendingApproval(request, operator, cycleId, "SPEC_DELTA");
    });
    await applyTokenAndReload(page, approver);
    await openStudio(page, projectId, cycleId, "SPEC_DELTA");
    await approveInDecisionPanel(page, "SPEC_DELTA");

    await poll("IMPACT_ANALYSIS with a complete assessment", 900_000, async () => {
      if ((await cycleState(request, operator, cycleId)) !== "IMPACT_ANALYSIS") return false;
      const ia = await apiGet<{ status: string }>(
        request,
        operator,
        `/delivery-cycles/${cycleId}/impact-assessments/latest`,
      );
      return ia?.status === "COMPLETE";
    });
    const ia = (await apiGet<{ architecture_delta_suggested: boolean }>(
      request,
      operator,
      `/delivery-cycles/${cycleId}/impact-assessments/latest`,
    ))!;
    expect(
      ia.architecture_delta_suggested,
      "impact did not suggest an architecture delta; the panel cannot be exercised",
    ).toBeTruthy();

    await applyTokenAndReload(page, operator);
    await openStudio(page, projectId, cycleId, "IMPACT_ANALYSIS");
    await expect(page.getByText(/Architecture change suggested/i)).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(/can't be approved until the backend persists deltas/i)).toHaveCount(0);
    await page.getByRole("button", { name: /Propose a delta/i }).click();
    const confirm = page.getByRole("button", { name: "Confirm send" });
    if (await confirm.isVisible().catch(() => false)) await confirm.click();

    await poll("ARCHITECTURE_DELTA approval pending", 1_200_000, async () => {
      await failIfTaskFailed(request, operator, cycleId);
      return pendingApproval(request, operator, cycleId, "ARCHITECTURE_DELTA");
    });
    await page.reload();
    await expect(page.getByText(/awaiting approval/i)).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("button", { name: /Propose a delta/i })).toHaveCount(0);
    await applyTokenAndReload(page, approver);
    await approveInDecisionPanel(page, "ARCHITECTURE_DELTA");

    await applyTokenAndReload(page, operator);
    await advance(page, request, operator, projectId, cycleId, "start_planning", 300_000);
    await poll("implementation-spec delta drafted after an approved delta", 1_200_000, async () => {
      await failIfTaskFailed(request, operator, cycleId);
      const tasks = await cycleTasks(request, operator, cycleId);
      const spec = tasks.filter((t) => /implementation/i.test(t.title));
      return spec.length > 0 && spec.every((t) => t.status === "COMPLETED");
    });
  });

  test("bug fix: repair IMPLEMENTATION_SPEC in the Decision panel at ROOT_CAUSE", { tag: "@live" }, async ({
    page,
    request,
  }) => {
    test.setTimeout(2_400_000);
    test.skip(!ctx.projectId, "brownfield onboarding did not run");
    const operator = operatorToken()!;
    const approver = approverToken()!;
    const { projectId } = ctx;

    await setBrowserToken(page, operator);
    await page.goto(`/projects/${projectId}`);
    await page.getByRole("button", { name: "New delivery cycle" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("radio", { name: "Bug Fix" }).click();
    await dialog.locator("label.ol-field").filter({ hasText: "Defect title" }).locator("input").fill(DEFECT_TITLE);
    await dialog.locator("label.ol-field").filter({ hasText: "Description" }).locator("textarea").fill(DEFECT_DESCRIPTION);
    await dialog.getByRole("button", { name: "Create delivery cycle" }).click();
    await page.waitForURL(/\/cycles\/[^/]+\/studio/, { timeout: 60_000 });
    const cycleId = page.url().match(/cycles\/([^/]+)\/studio/)![1]!;

    await openStudio(page, projectId, cycleId, "TRIAGE");
    await expect(page.getByRole("button", { name: /Reject defect/i })).toBeVisible({ timeout: 120_000 });

    await reachBugFixStage(page, request, operator, projectId, cycleId, "start_reproduction", "REPRODUCTION", 600_000);
    await reachBugFixStage(page, request, operator, projectId, cycleId, "resolve_expected_behavior", "EXPECTED_BEHAVIOR", 1_200_000);
    await reachBugFixStage(page, request, operator, projectId, cycleId, "start_root_cause", "ROOT_CAUSE", 900_000);

    await poll("repair IMPLEMENTATION_SPEC approval pending", 1_200_000, async () => {
      await failIfTaskFailed(request, operator, cycleId);
      return pendingApproval(request, operator, cycleId, "IMPLEMENTATION_SPEC");
    });
    await applyTokenAndReload(page, approver);
    await openStudio(page, projectId, cycleId, "ROOT_CAUSE");
    const panel = page.locator(".ol-decision-panel");
    await expect(panel).toBeVisible({ timeout: 120_000 });
    await expect(panel).toContainText("IMPLEMENTATION_SPEC");
    await expect(panel.getByRole("button", { name: "Approve" })).toBeEnabled();
  });
});
