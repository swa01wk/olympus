import type { APIRequestContext, Page } from "@playwright/test";
import { expect } from "@playwright/test";
import { randomUUID } from "node:crypto";

export function apiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_OLYMPUS_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
}

export function operatorToken(): string | undefined {
  return process.env.OLYMPUS_OPERATOR_TOKEN ?? process.env.OLYMPUS_STUDIO_OPERATOR_TOKEN;
}

export function approverToken(): string | undefined {
  return process.env.OLYMPUS_APPROVER_TOKEN ?? process.env.OLYMPUS_STUDIO_APPROVER_TOKEN;
}

export function liveStudioConfigured(): boolean {
  return Boolean(operatorToken() && approverToken());
}

export async function apiReachable(request: APIRequestContext): Promise<boolean> {
  try {
    const res = await request.get(`${apiBaseUrl()}/health`, { timeout: 5_000 });
    return res.ok();
  } catch {
    return false;
  }
}

function authHeaders(token: string, idempotencyKey?: string): Record<string, string> {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    Accept: "application/json",
  };
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
  return headers;
}

/** Per-request cap so a hung API does not block the overall poll deadline. */
const LIVE_API_GET_TIMEOUT_MS = 60_000;

function isTransientApiRequestError(err: unknown): boolean {
  const message = err instanceof Error ? err.message : String(err);
  return /socket hang up|ECONNRESET|ECONNREFUSED|ETIMEDOUT|timeout/i.test(message);
}

/** GET that returns null on transient connection errors (live stack may restart under load). */
async function apiGetOrNull(
  request: APIRequestContext,
  url: string,
  token: string,
): Promise<Awaited<ReturnType<APIRequestContext["get"]>> | null> {
  try {
    return await request.get(url, {
      headers: authHeaders(token),
      timeout: LIVE_API_GET_TIMEOUT_MS,
    });
  } catch (err) {
    if (isTransientApiRequestError(err)) return null;
    throw err;
  }
}

export async function createProject(request: APIRequestContext, token: string): Promise<string> {
  const key = `STU${Date.now().toString(36).toUpperCase().slice(-6)}`;
  const res = await request.post(`${apiBaseUrl()}/projects`, {
    headers: authHeaders(token, randomUUID()),
    data: { key, name: `Studio E2E ${key}` },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = (await res.json()) as { id: string };
  return body.id;
}

export async function createGreenfieldCycle(
  request: APIRequestContext,
  token: string,
  projectId: string,
): Promise<string> {
  const res = await request.post(`${apiBaseUrl()}/projects/${projectId}/delivery-cycles`, {
    headers: authHeaders(token, randomUUID()),
    data: { type: "GREENFIELD_BUILD", objective: "Studio greenfield E2E" },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = (await res.json()) as { id: string };
  return body.id;
}

export async function waitForFeatures(
  request: APIRequestContext,
  token: string,
  projectId: string,
  minCount: number,
  timeoutMs: number,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const res = await apiGetOrNull(request, `${apiBaseUrl()}/projects/${projectId}/features`, token);
    if (res?.ok()) {
      const rows = (await res.json()) as unknown[];
      if (rows.length >= minCount) return;
    }
    await new Promise((r) => setTimeout(r, 3_000));
  }
  throw new Error(`Timed out waiting for ${minCount} feature(s)`);
}

async function decomposeDiagnostics(
  request: APIRequestContext,
  token: string,
  cycleId: string,
): Promise<string> {
  const parts: string[] = [];
  const tasksRes = await apiGetOrNull(
    request,
    `${apiBaseUrl()}/delivery-cycles/${cycleId}/tasks`,
    token,
  );
  if (tasksRes?.ok()) {
    const tasks = (await tasksRes.json()) as {
      title: string;
      status: string;
      blocked_reason: string | null;
    }[];
    parts.push(`tasks=${JSON.stringify(tasks)}`);
  }
  const decRes = await apiGetOrNull(
    request,
    `${apiBaseUrl()}/delivery-cycles/${cycleId}/decompositions`,
    token,
  );
  if (decRes?.ok()) {
    parts.push(`decompositions=${JSON.stringify(await decRes.json())}`);
  }
  return parts.join(" ");
}

/** Poll until at least one product source exists (after chat PRD attach). */
export async function waitForProjectSources(
  request: APIRequestContext,
  token: string,
  projectId: string,
  minCount: number,
  timeoutMs: number,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const sourcesRes = await apiGetOrNull(
      request,
      `${apiBaseUrl()}/projects/${projectId}/sources`,
      token,
    );
    if (sourcesRes?.ok()) {
      const sources = (await sourcesRes.json()) as unknown[];
      if (sources.length >= minCount) return;
    }
    await new Promise((r) => setTimeout(r, 1_000));
  }
  throw new Error(`Timed out waiting for ${minCount} product source(s)`);
}

/** POST /sources/{id}/decompose for the latest project source (reliable vs UI-only). */
export async function decomposeLatestSourceViaApi(
  request: APIRequestContext,
  token: string,
  projectId: string,
  cycleId: string,
): Promise<string> {
  const sourcesRes = await request.get(`${apiBaseUrl()}/projects/${projectId}/sources`, {
    headers: authHeaders(token),
  });
  expect(sourcesRes.ok(), await sourcesRes.text()).toBeTruthy();
  const sources = (await sourcesRes.json()) as { id: string; version: number; title: string }[];
  expect(sources.length, "upload PRD before decompose").toBeGreaterThan(0);
  const latest = [...sources].sort((a, b) => b.version - a.version)[0]!;
  const decRes = await request.post(`${apiBaseUrl()}/sources/${latest.id}/decompose`, {
    headers: authHeaders(token, randomUUID()),
    data: { delivery_cycle_id: cycleId },
  });
  expect(decRes.ok(), await decRes.text()).toBeTruthy();
  const body = (await decRes.json()) as { task_id?: string };
  expect(body.task_id, JSON.stringify(body)).toBeTruthy();
  return body.task_id!;
}

/** Poll features after Kira decompose; fail fast if decomposition reports FAILED. */
export async function waitForLiveDecomposeFeatures(
  request: APIRequestContext,
  token: string,
  projectId: string,
  cycleId: string,
  minCount: number,
  timeoutMs: number,
): Promise<void> {
  const started = Date.now();
  const deadline = started + timeoutMs;
  let sawDecomposeTask = false;
  while (Date.now() < deadline) {
    await answerOpenClarificationsForCycle(request, token, cycleId);

    const tasksRes = await apiGetOrNull(
      request,
      `${apiBaseUrl()}/delivery-cycles/${cycleId}/tasks`,
      token,
    );
    if (tasksRes?.ok()) {
      const tasks = (await tasksRes.json()) as { title: string; status: string }[];
      if (tasks.some((t) => /decompose/i.test(t.title))) sawDecomposeTask = true;
      const failedTask = tasks.find((t) => t.status === "FAILED" || t.status === "CANCELLED");
      if (failedTask) {
        throw new Error(
          `Decompose task failed (${failedTask.status}): ${failedTask.title}; ${await decomposeDiagnostics(request, token, cycleId)}`,
        );
      }
    }

    const decRes = await apiGetOrNull(
      request,
      `${apiBaseUrl()}/delivery-cycles/${cycleId}/decompositions`,
      token,
    );
    if (decRes?.ok()) {
      const rows = (await decRes.json()) as { status: string; validation_report?: unknown }[];
      const failed = rows.find((d) => d.status === "FAILED");
      if (failed) {
        throw new Error(
          `Product decomposition failed: ${JSON.stringify(failed.validation_report ?? failed)}`,
        );
      }
    }
    const featRes = await apiGetOrNull(
      request,
      `${apiBaseUrl()}/projects/${projectId}/features`,
      token,
    );
    if (featRes?.ok()) {
      const features = (await featRes.json()) as unknown[];
      if (features.length >= minCount) return;
    }

    const elapsed = Date.now() - started;
    if (!sawDecomposeTask && elapsed > 180_000) {
      throw new Error(
        `Decompose task never appeared within 3m (check scheduler/execution-worker logs and .env LLM keys). ${await decomposeDiagnostics(request, token, cycleId)}`,
      );
    }

    await new Promise((r) => setTimeout(r, 5_000));
  }
  throw new Error(
    `Timed out waiting for ${minCount} feature(s) after decompose (cycle ${cycleId}). ${await decomposeDiagnostics(request, token, cycleId)}`,
  );
}

const SCOPE_ELIGIBLE = new Set(["PROPOSED", "DRAFT"]);

async function verifyScopeSpecIds(
  request: APIRequestContext,
  token: string,
  specIds: string[],
): Promise<string[]> {
  const verified: string[] = [];
  for (const id of specIds) {
    const res = await request.get(`${apiBaseUrl()}/specs/${id}`, {
      headers: authHeaders(token),
    });
    if (!res.ok()) continue;
    const body = (await res.json()) as { status: string };
    if (SCOPE_ELIGIBLE.has(body.status)) verified.push(id);
  }
  return verified;
}

export async function waitForScopeEligibleSpecIds(
  request: APIRequestContext,
  token: string,
  projectId: string,
  timeoutMs: number,
): Promise<string[]> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const featRes = await apiGetOrNull(
      request,
      `${apiBaseUrl()}/projects/${projectId}/features`,
      token,
    );
    if (featRes?.ok()) {
      const features = (await featRes.json()) as { id: string }[];
      const ids: string[] = [];
      for (const f of features) {
        const specRes = await apiGetOrNull(
          request,
          `${apiBaseUrl()}/features/${f.id}/specs`,
          token,
        );
        if (!specRes?.ok()) continue;
        const specs = (await specRes.json()) as { id: string; status: string; version: number }[];
        const eligible = specs.filter((s) => SCOPE_ELIGIBLE.has(s.status));
        if (eligible.length === 0) continue;
        eligible.sort((a, b) => b.version - a.version);
        ids.push(eligible[0]!.id);
      }
      const verified = await verifyScopeSpecIds(request, token, ids);
      if (verified.length > 0) return verified;
    }
    await new Promise((r) => setTimeout(r, 3_000));
  }
  throw new Error("Timed out waiting for PROPOSED/DRAFT feature specs");
}

const DEFAULT_CLARIFICATION_ANSWER =
  "Out of scope for the MVP unless the PRD states it. Choose the simplest reasonable default, " +
  "record it as an assumption, and do not block on it.";

/**
 * SupportDesk answers keyed by question keywords, most specific first. An answer that does not
 * address the question makes Kira re-ask it on the next redecompose.
 */
const CLARIFICATION_ANSWERS: { match: RegExp; answer: string }[] = [
  {
    match: /not found|non-existent|nonexistent|does not exist|doesn't exist|unknown (ticket )?id/,
    answer: 'Return HTTP 404 Not Found with body {"detail": "Ticket not found"}.',
  },
  {
    match: /invalid|unsupported|unknown status|validation/,
    answer:
      "The status filter and status updates accept only OPEN, IN_PROGRESS, or CLOSED. Any other " +
      "value is rejected with HTTP 422 and a FastAPI-style validation error body.",
  },
  {
    match: /transition|statuses|status values|allowed status|lifecycle/,
    answer:
      "Statuses are OPEN, IN_PROGRESS, CLOSED. Allowed transitions: OPEN→IN_PROGRESS, " +
      "OPEN→CLOSED, IN_PROGRESS→OPEN, IN_PROGRESS→CLOSED. CLOSED is terminal: any update to a " +
      "CLOSED ticket returns HTTP 409 Conflict.",
  },
  {
    match: /closed|409|modif/,
    answer: "Closed tickets cannot be modified; any update returns HTTP 409 Conflict.",
  },
  {
    match: /http method|path|route|endpoint|response code|status code|response shape/,
    answer:
      "JSON REST API: POST /tickets → 201 with the ticket; GET /tickets?status= → 200 list; " +
      "GET /tickets/{id} → 200 or 404; PATCH /tickets/{id}/status → 200, 404, 409 or 422; " +
      'POST /tickets/{id}/close → 200, 404 or 409; GET /health → 200 {"status": "ok"}.',
  },
  {
    match: /health|readiness/,
    answer: 'GET /health returns 200 {"status": "ok"} when the database is reachable, else 503.',
  },
  {
    match: /paginat|sort|order/,
    answer: "No pagination in the MVP; list returns all tickets ordered by creation time ascending.",
  },
  {
    match: /subject|description|required|length|empty/,
    answer:
      "Subject (max 200 chars) and description are required non-empty strings; missing or empty " +
      "values return HTTP 422.",
  },
  {
    match: /auth|login|permission|role/,
    answer: "No authentication or roles in the MVP; the API is internal-only.",
  },
  {
    match: /priority|sla|assign|notification|email/,
    answer: "Out of scope for the MVP.",
  },
];

function pickClarificationAnswer(question: string): string {
  const q = question.toLowerCase();
  return CLARIFICATION_ANSWERS.find((a) => a.match.test(q))?.answer ?? DEFAULT_CLARIFICATION_ANSWER;
}

type InboxClarification = { id: string; status: string; question?: string };

async function listOpenClarificationsFromInbox(
  request: APIRequestContext,
  token: string,
  cycleId: string,
): Promise<InboxClarification[]> {
  const res = await apiGetOrNull(
    request,
    `${apiBaseUrl()}/views/inbox?delivery_cycle_id=${cycleId}`,
    token,
  );
  if (!res?.ok()) return [];
  const items = (await res.json()) as {
    kind: string;
    clarification?: InboxClarification;
  }[];
  return items
    .filter((item) => item.kind === "CLARIFICATION" && item.clarification?.status === "OPEN")
    .map((item) => item.clarification!);
}

/** Answer inbox clarifications; returns true if any answer triggered product redecompose. */
export async function answerOpenClarificationsForCycle(
  request: APIRequestContext,
  token: string,
  cycleId: string,
): Promise<boolean> {
  const open = await listOpenClarificationsFromInbox(request, token, cycleId);
  let redecompose = false;
  for (const cl of open) {
    const res = await request.post(
      `${apiBaseUrl()}/clarifications/${cl.id}/answer`,
      {
        headers: authHeaders(token, randomUUID()),
        data: { answer: pickClarificationAnswer(cl.question ?? cl.id) },
      },
    );
    expect(res.ok(), await res.text()).toBeTruthy();
    const body = (await res.json()) as { redecompose_task_id?: string };
    if (body.redecompose_task_id) redecompose = true;
  }
  return redecompose;
}

const IN_FLIGHT_TASK_STATUSES = new Set(["READY", "QUEUED", "RUNNING"]);

/**
 * Wait until no decompose task in the cycle is queued or running. Each clarification answer
 * queues its own redecompose, and those can open new blocking clarifications when they finish.
 */
async function waitForDecomposeIdle(
  request: APIRequestContext,
  token: string,
  cycleId: string,
  timeoutMs: number,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const res = await apiGetOrNull(
      request,
      `${apiBaseUrl()}/delivery-cycles/${cycleId}/tasks`,
      token,
    );
    if (res?.ok()) {
      const decomposeTasks = (
        (await res.json()) as { key: string; title: string; status: string }[]
      ).filter((t) => /decompose/i.test(t.title));
      if (!decomposeTasks.some((t) => IN_FLIGHT_TASK_STATUSES.has(t.status))) {
        const taskSeq = (key: string) => Number(key.replace(/\D/g, "")) || 0;
        const latest = [...decomposeTasks].sort((a, b) => taskSeq(b.key) - taskSeq(a.key))[0];
        if (latest?.status === "FAILED") {
          throw new Error(
            `Latest decompose task ${latest.key} failed; ${await decomposeDiagnostics(request, token, cycleId)}`,
          );
        }
        return;
      }
    }
    await new Promise((r) => setTimeout(r, 5_000));
  }
  throw new Error(
    `Timed out waiting for decompose tasks to finish (cycle ${cycleId}). ${await decomposeDiagnostics(request, token, cycleId)}`,
  );
}

/**
 * Answer clarifications until none remain and no redecompose is in flight.
 * Live Kira can open new blocking clarifications after redecompose — loop until stable.
 */
export async function settleOpenClarificationsForCycle(
  request: APIRequestContext,
  token: string,
  _projectId: string,
  cycleId: string,
  timeoutMs: number,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let clearStreak = 0;
  while (Date.now() < deadline) {
    await waitForDecomposeIdle(request, token, cycleId, Math.max(0, deadline - Date.now()));
    const open = await listOpenClarificationsFromInbox(request, token, cycleId);
    if (open.length === 0) {
      clearStreak += 1;
      if (clearStreak >= 2) return;
      await new Promise((r) => setTimeout(r, 4_000));
      continue;
    }
    clearStreak = 0;
    await answerOpenClarificationsForCycle(request, token, cycleId);
    await new Promise((r) => setTimeout(r, 3_000));
  }
  const stillOpen = await listOpenClarificationsFromInbox(request, token, cycleId);
  throw new Error(
    `Timed out settling clarifications for cycle ${cycleId} (${stillOpen.length} still OPEN)`,
  );
}

function isRetryableGuardFailure(bodyText: string): boolean {
  return (
    bodyText.includes("GUARD_FAILED") ||
    bodyText.includes("BLOCKING_CLARIFICATION_OPEN") ||
    bodyText.includes("SCOPE_NOT_APPROVED") ||
    bodyText.includes("SCOPE_HASH_MISMATCH")
  );
}

async function fetchTransitionPreview(
  request: APIRequestContext,
  token: string,
  cycleId: string,
  commandName: string,
): Promise<TransitionPreviewRow | undefined> {
  const previewRes = await apiGetOrNull(
    request,
    `${apiBaseUrl()}/delivery-cycles/${cycleId}/next-transitions`,
    token,
  );
  if (!previewRes?.ok()) return undefined;
  const previews = (await previewRes.json()) as TransitionPreviewRow[];
  return previews.find((p) => p.command === commandName);
}

/** scope_approved guard must not report BLOCKING_CLARIFICATION_OPEN before scope sign-off. */
export async function waitForNoBlockingClarificationsOnScopeGuard(
  request: APIRequestContext,
  token: string,
  cycleId: string,
  timeoutMs: number,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const preview = await fetchTransitionPreview(request, token, cycleId, "start_architecture");
    const scopeGuard = preview?.guard_results?.find((g) => g.guard_id === "scope_approved");
    const blocking = scopeGuard?.reasons?.includes("BLOCKING_CLARIFICATION_OPEN");
    if (!blocking) return;
    await new Promise((r) => setTimeout(r, 3_000));
  }
  throw new Error(
    `Timed out waiting for blocking clarifications to clear (cycle ${cycleId})`,
  );
}

export async function getCycleState(
  request: APIRequestContext,
  token: string,
  cycleId: string,
): Promise<string> {
  const res = await request.get(`${apiBaseUrl()}/delivery-cycles/${cycleId}`, {
    headers: authHeaders(token),
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = (await res.json()) as { state: string };
  return body.state;
}

type TransitionPreviewRow = {
  command: string;
  allowed: boolean;
  guard_results?: { guard_id: string; ok: boolean; reasons: string[] }[];
};

function guardsFullyOk(preview: TransitionPreviewRow | undefined): boolean {
  if (!preview?.allowed) return false;
  return (preview.guard_results ?? []).every((g) => g.ok);
}

/** POST /delivery-cycles/{id}/commands/{name} once next-transitions shows it allowed. */
export async function runCycleCommandWhenAllowed(
  request: APIRequestContext,
  token: string,
  cycleId: string,
  commandName: string,
  timeoutMs: number,
  opts?: { answerClarifications?: boolean },
): Promise<void> {
  const answerClarifications = opts?.answerClarifications ?? false;
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (answerClarifications) {
      await answerOpenClarificationsForCycle(request, token, cycleId);
    }
    const state = await getCycleState(request, token, cycleId);
    const previewRes = await request.get(
      `${apiBaseUrl()}/delivery-cycles/${cycleId}/next-transitions`,
      { headers: authHeaders(token) },
    );
    if (previewRes.ok()) {
      const previews = (await previewRes.json()) as TransitionPreviewRow[];
      const match = previews.find((p) => p.command === commandName);
      if (guardsFullyOk(match)) {
        const res = await request.post(
          `${apiBaseUrl()}/delivery-cycles/${cycleId}/commands/${commandName}`,
          {
            headers: authHeaders(token, randomUUID()),
            data: { expected_state: state, payload: null },
          },
        );
        if (res.ok()) return;
        const bodyText = await res.text();
        if (isRetryableGuardFailure(bodyText)) {
          await new Promise((r) => setTimeout(r, 3_000));
          continue;
        }
        expect(res.ok(), bodyText).toBeTruthy();
      }
    }
    await new Promise((r) => setTimeout(r, 3_000));
  }
  let detail = "";
  try {
    const state = await getCycleState(request, token, cycleId);
    const previewRes = await request.get(
      `${apiBaseUrl()}/delivery-cycles/${cycleId}/next-transitions`,
      { headers: authHeaders(token) },
    );
    if (previewRes.ok()) {
      const previews = (await previewRes.json()) as {
        command: string;
        allowed: boolean;
        guard_results?: { guard_id: string; ok: boolean; reasons: string[] }[];
      }[];
      const match = previews.find((p) => p.command === commandName);
      detail = ` cycle_state=${state} preview=${JSON.stringify(match ?? previews)}`;
    } else {
      detail = ` cycle_state=${state}`;
    }
  } catch {
    /* best-effort */
  }
  throw new Error(`Timed out waiting for allowed command ${commandName}${detail}`);
}

export async function requestScopeApprovalViaApi(
  request: APIRequestContext,
  token: string,
  cycleId: string,
  featureSpecIds: string[],
): Promise<string> {
  const res = await request.post(
    `${apiBaseUrl()}/delivery-cycles/${cycleId}/scope/approval-request`,
    {
      headers: authHeaders(token, randomUUID()),
      data: { feature_spec_ids: featureSpecIds },
    },
  );
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = (await res.json()) as { approval_id?: string };
  expect(body.approval_id, JSON.stringify(body)).toBeTruthy();
  return body.approval_id!;
}

export async function approveScopeViaApi(
  request: APIRequestContext,
  approverToken: string,
  approvalId: string,
): Promise<void> {
  const res = await request.post(`${apiBaseUrl()}/approvals/${approvalId}/decision`, {
    headers: authHeaders(approverToken, randomUUID()),
    data: { decision: "APPROVED", note: "Studio E2E scope sign-off" },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
}

export async function waitForArchitectureVersion(
  request: APIRequestContext,
  token: string,
  projectId: string,
  minVersion: number,
  timeoutMs: number,
): Promise<{ id: string; version: number; status: string }> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const res = await apiGetOrNull(
      request,
      `${apiBaseUrl()}/projects/${projectId}/architecture?latest=true`,
      token,
    );
    if (res?.ok()) {
      const body = (await res.json()) as { id: string; version: number; status: string } | null;
      if (body && body.version >= minVersion) return body;
    }
    await new Promise((r) => setTimeout(r, 5_000));
  }
  throw new Error(`Timed out waiting for architecture v${minVersion}+`);
}

export async function setBrowserToken(page: Page, token: string) {
  await page.addInitScript((t) => {
    window.localStorage.setItem("olympus_api_token", t);
  }, token);
}

/** Switch actor token; must re-register init script so reload does not restore an earlier token. */
export async function applyTokenAndReload(page: Page, token: string) {
  await setBrowserToken(page, token);
  await page.reload();
}

/** Upload PRD, decompose, approve scope, and transition to ARCHITECTURE (live worker must be running). */
export async function bootstrapGreenfieldToArchitecture(
  page: Page,
  request: APIRequestContext,
  opts: {
    operator: string;
    approver: string;
    projectId: string;
    cycleId: string;
    prdPath: string;
  },
): Promise<void> {
  const { operator, approver, projectId, cycleId, prdPath } = opts;

  await setBrowserToken(page, operator);
  await page.goto(`/projects/${projectId}/cycles/${cycleId}/studio`);
  await expect(page.getByRole("heading", { name: /Discovery/i })).toBeVisible({ timeout: 60_000 });

  const chatFileInput = page.locator(".ol-chat-composer input[type=file]");
  await page.getByRole("button", { name: "Attach PRD" }).click();
  await chatFileInput.setInputFiles(prdPath);
  // Avoid matching Discovery copy "PRD versions ingested…" (contains "PRD v").
  await expect(page.locator(".ol-chat-system").getByText(/PRD v\d+ ingested/i)).toBeVisible({
    timeout: 120_000,
  });
  await waitForProjectSources(request, operator, projectId, 1, 120_000);

  await decomposeLatestSourceViaApi(request, operator, projectId, cycleId);

  await waitForLiveDecomposeFeatures(request, operator, projectId, cycleId, 1, 1_200_000);
  await settleOpenClarificationsForCycle(request, operator, projectId, cycleId, 900_000);
  await runCycleCommandWhenAllowed(request, operator, cycleId, "start_product_modeling", 300_000);

  await page
    .getByRole("list", { name: "Delivery stages" })
    .getByRole("button", { name: /^PRODUCT MODEL/ })
    .click();
  await expect(page.getByText("Capabilities & features")).toBeVisible({ timeout: 30_000 });

  const featuresPanel = page.locator(".ol-ws-split").first();
  const featureBtn = featuresPanel.getByRole("button", { name: /^FEAT-/ }).first();
  await expect(featureBtn).toBeVisible({ timeout: 30_000 });
  await featureBtn.click();

  await page.getByRole("button", { name: "Edit spec" }).click();
  const summary = page.locator(".ol-ws-spec-form textarea").first();
  await summary.fill("Studio RL2 smoke — scope review summary.");
  await page.getByRole("button", { name: "Save new version" }).click();
  await expect(page.getByText(/Studio RL2 smoke/i)).toBeVisible({ timeout: 30_000 });

  await settleOpenClarificationsForCycle(request, operator, projectId, cycleId, 900_000);
  await waitForNoBlockingClarificationsOnScopeGuard(request, operator, cycleId, 300_000);

  const scopeSpecIds = await waitForScopeEligibleSpecIds(request, operator, projectId, 300_000);
  const scopeApprovalId = await requestScopeApprovalViaApi(
    request,
    operator,
    cycleId,
    scopeSpecIds,
  );
  await approveScopeViaApi(request, approver, scopeApprovalId);
  await waitForNoBlockingClarificationsOnScopeGuard(request, operator, cycleId, 120_000);

  // Do not answer clarifications after scope approval — answers can trigger redecompose and break scope hash.
  await runCycleCommandWhenAllowed(request, operator, cycleId, "start_architecture", 600_000);

  await applyTokenAndReload(page, operator);
  await page.goto(`/projects/${projectId}/cycles/${cycleId}/studio?stage=ARCHITECTURE`);
  await expect(page.getByRole("heading", { name: /^Architecture$/i })).toBeVisible({
    timeout: 60_000,
  });
}
