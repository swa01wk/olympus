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
    const res = await request.get(`${apiBaseUrl()}/projects/${projectId}/features`, {
      headers: authHeaders(token),
    });
    if (res.ok()) {
      const rows = (await res.json()) as unknown[];
      if (rows.length >= minCount) return;
    }
    await new Promise((r) => setTimeout(r, 3_000));
  }
  throw new Error(`Timed out waiting for ${minCount} feature(s)`);
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
