import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { IntakeFormDialog, secretNameForRepo } from "@/components/dialogs/IntakeFormDialog";
import type {
  MaterializationAttempt,
  Repository,
  RepositoryStatus,
} from "@/src/api/types/repository";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

const TOKEN = "ghp_super_secret_token";

type Call = {
  method: string;
  path: string;
  body: unknown;
  headers: Record<string, string>;
};

type ServerState = {
  roles: string[];
  repos: Repository[];
  materializations: MaterializationAttempt[];
  registerErrors: { code: string; message: string }[];
};

let server: ServerState;
let calls: Call[];
let streamController: ReadableStreamDefaultController<Uint8Array> | null;
let streamAborted: boolean;

function repository(id: string, status: RepositoryStatus, overrides: Partial<Repository> = {}) {
  return {
    id,
    project_id: "proj-1",
    name: "app",
    source_type: "EXTERNAL_CLONE",
    provider: "GITHUB",
    remote_url: "https://github.com/org/app.git",
    default_branch: "main",
    registered_sha: null,
    canonical_commit: status === "READY" ? "abc123" : null,
    released_commit: null,
    status,
    status_reason: null,
    credential_ref: "none:",
    credential_status: "OK",
    workspace: null,
    ...overrides,
  } satisfies Repository;
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function setRepoStatus(id: string, status: RepositoryStatus) {
  server.repos = server.repos.map((r) =>
    r.id === id ? { ...r, status, canonical_commit: status === "READY" ? "abc123" : null } : r,
  );
}

async function fakeFetch(input: string, init: RequestInit = {}) {
  const url = new URL(input);
  const method = init.method ?? "GET";
  const path = url.pathname;
  calls.push({
    method,
    path: `${path}${url.search}`,
    body: typeof init.body === "string" ? JSON.parse(init.body) : undefined,
    headers: (init.headers as Record<string, string>) ?? {},
  });

  if (path === "/events/stream") {
    streamAborted = false;
    init.signal?.addEventListener("abort", () => {
      streamAborted = true;
      streamController?.error(new DOMException("Aborted", "AbortError"));
    });
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        streamController = controller;
      },
    });
    return { ok: true, status: 200, body } as unknown as Response;
  }
  if (path === "/actors/me") {
    return json({ actor_id: "actor-1", kind: "HUMAN", name: "dev", roles: server.roles });
  }
  if (path === "/projects/proj-1") {
    return json({ id: "proj-1", key: "PRJ", name: "Demo", description: null });
  }
  if (path === "/projects/proj-1/repositories" && method === "GET") return json(server.repos);
  if (path === "/projects/proj-1/repositories" && method === "POST") {
    const failure = server.registerErrors.shift();
    if (failure) return json(failure, 422);
    const body = JSON.parse(init.body as string) as { name: string; credential_ref: string };
    const repo = repository("repo-new", "CLONING", {
      name: body.name,
      credential_ref: body.credential_ref,
    });
    server.repos = [repo];
    return json(repo, 201);
  }
  if (path.startsWith("/secrets/") && method === "PUT") {
    return json({ credential_ref: `secret:${decodeURIComponent(path.slice("/secrets/".length))}` });
  }
  if (path === "/projects/proj-1/delivery-cycles" && method === "POST") {
    return json({ id: "cycle-bf" }, 201);
  }
  if (path === "/projects/proj-1/change-requests" && method === "POST") {
    return json({ status: "ACCEPTED", result: { delivery_cycle_id: "cycle-fc" } });
  }
  if (path === "/projects/proj-1/defects" && method === "POST") {
    return json({ status: "REJECTED", reason: "PROJECT_NOT_CHANGE_READY" });
  }
  const retry = path.match(/^\/repositories\/([^/]+)\/commands\/retry_materialization$/);
  if (retry && method === "POST") {
    setRepoStatus(retry[1], "CLONING");
    return json(server.repos.find((r) => r.id === retry[1]));
  }
  const mats = path.match(/^\/repositories\/([^/]+)\/materializations$/);
  if (mats) return json(server.materializations);
  const detail = path.match(/^\/repositories\/([^/]+)$/);
  if (detail) {
    const repo = server.repos.find((r) => r.id === detail[1]);
    return repo ? json(repo) : json({ code: "NOT_FOUND", message: "Repository not found" }, 404);
  }
  return json({ code: "NOT_FOUND", message: `unmocked ${method} ${path}` }, 404);
}

function emitEvent(sequence: number, eventType: string, payload: Record<string, unknown>) {
  const data = JSON.stringify({ id: `evt-${sequence}`, sequence, event_type: eventType, payload });
  streamController?.enqueue(
    new TextEncoder().encode(`id: ${sequence}\nevent: message\ndata: ${data}\n\n`),
  );
}

function callsTo(method: string, path: string) {
  return calls.filter((c) => c.method === method && c.path === path);
}

function renderDialog(props: { open?: boolean } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const ui = (open: boolean) => (
    <QueryClientProvider client={client}>
      <IntakeFormDialog open={open} projectId="proj-1" onClose={() => {}} />
    </QueryClientProvider>
  );
  const result = render(ui(props.open ?? true));
  return { client, ...result, setOpen: (open: boolean) => result.rerender(ui(open)) };
}

function inputAfterLabel(label: string): HTMLInputElement {
  const span = screen.getByText(label);
  const field = span.closest("label");
  const input = field?.querySelector("input, textarea, select");
  if (!input) throw new Error(`No input for label ${label}`);
  return input as HTMLInputElement;
}

async function openBrownfield() {
  fireEvent.click(screen.getByRole("radio", { name: "Brownfield Onboarding" }));
  await waitFor(() => expect(callsTo("GET", "/projects/proj-1/repositories")).not.toHaveLength(0));
}

async function fillRegistration(name: string, remoteUrl: string, token?: string) {
  await waitFor(() => expect(screen.getByRole("radio", { name: "Register new" })).toBeTruthy());
  fireEvent.click(screen.getByRole("radio", { name: "Register new" }));
  fireEvent.change(inputAfterLabel("Name"), { target: { value: name } });
  fireEvent.change(inputAfterLabel("Remote URL"), { target: { value: remoteUrl } });
  if (token) {
    fireEvent.change(inputAfterLabel("Access token (optional, sent once)"), {
      target: { value: token },
    });
  }
}

async function confirmRegister() {
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Register repository" })).toHaveProperty(
      "disabled",
      false,
    ),
  );
  fireEvent.click(screen.getByRole("button", { name: "Register repository" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm send" }));
}

function storageContains(value: string): boolean {
  for (const storage of [window.localStorage, window.sessionStorage]) {
    for (let i = 0; i < storage.length; i += 1) {
      const key = storage.key(i)!;
      if (key.includes(value) || (storage.getItem(key) ?? "").includes(value)) return true;
    }
  }
  return false;
}

beforeEach(() => {
  server = { roles: ["OPERATOR"], repos: [], materializations: [], registerErrors: [] };
  calls = [];
  streamController = null;
  streamAborted = false;
  vi.stubGlobal("fetch", vi.fn(fakeFetch));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
  window.localStorage.clear();
  window.sessionStorage.clear();
});

describe("secretNameForRepo", () => {
  it("slugifies to the credential_ref charset", () => {
    expect(secretNameForRepo("PRJ", "My App!! (v2)")).toBe("repo-prj-my-app-v2");
    expect(secretNameForRepo("PRJ", "svc/api.core_x")).toBe("repo-prj-svc-api.core_x");
  });

  it("caps the name at 120 characters without a trailing separator", () => {
    const name = secretNameForRepo("PRJ", `${"a".repeat(114)}-${"b".repeat(50)}`);
    expect(name.length).toBeLessThanOrEqual(120);
    expect(name).toMatch(/^[a-z0-9_.-]+$/);
    expect(name).not.toMatch(/[-.]$/);
  });
});

describe("IntakeFormDialog change request and defect intake", () => {
  it("feature change posts a change request and opens the cycle it created", async () => {
    renderDialog();
    fireEvent.click(screen.getByRole("radio", { name: "Feature Change" }));
    fireEvent.change(inputAfterLabel("Change request title"), {
      target: { value: "Ticket priority" },
    });
    fireEvent.change(inputAfterLabel("Description"), { target: { value: "Add LOW/MEDIUM/HIGH" } });
    const create = screen.getByRole("button", { name: "Create delivery cycle" });
    await waitFor(() => expect(create).toHaveProperty("disabled", false));
    fireEvent.click(create);

    await waitFor(() => expect(push).toHaveBeenCalledWith("/projects/proj-1/cycles/cycle-fc/studio"));
    const [post] = callsTo("POST", "/projects/proj-1/change-requests");
    expect(post.body).toEqual({
      title: "Ticket priority",
      description: "Add LOW/MEDIUM/HIGH",
      external_ref: null,
    });
    expect(post.headers["Idempotency-Key"]).toBeTruthy();
    expect(callsTo("POST", "/projects/proj-1/delivery-cycles")).toHaveLength(0);
  });

  it("bug fix shows the intake rejection reason", async () => {
    renderDialog();
    fireEvent.click(screen.getByRole("radio", { name: "Bug Fix" }));
    fireEvent.change(inputAfterLabel("Defect title"), { target: { value: "Closed update 500" } });
    fireEvent.change(inputAfterLabel("Description"), { target: { value: "PATCH returns 500" } });
    const create = screen.getByRole("button", { name: "Create delivery cycle" });
    await waitFor(() => expect(create).toHaveProperty("disabled", false));
    fireEvent.click(create);

    expect(await screen.findByText(/Intake REJECTED: PROJECT_NOT_CHANGE_READY/)).toBeTruthy();
    expect(push).not.toHaveBeenCalled();
  });
});

describe("IntakeFormDialog brownfield", () => {
  it("register → materializing → READY → create cycle; token never cached or stored", async () => {
    const { client } = renderDialog();
    await openBrownfield();
    await fillRegistration("My App", "https://github.com/org/app.git", TOKEN);

    expect(screen.getByText("PUT /secrets/repo-prj-my-app · value=…")).toBeTruthy();
    expect(screen.getByText("credential_ref=secret:repo-prj-my-app")).toBeTruthy();

    await confirmRegister();
    await waitFor(() => expect(callsTo("POST", "/projects/proj-1/repositories")).toHaveLength(1));

    const puts = callsTo("PUT", "/secrets/repo-prj-my-app");
    expect(puts).toHaveLength(1);
    expect(puts[0].body).toEqual({ value: TOKEN });
    expect(callsTo("POST", "/projects/proj-1/repositories")[0].body).toEqual({
      name: "My App",
      provider: "GITHUB",
      remote_url: "https://github.com/org/app.git",
      default_branch: null,
      credential_ref: "secret:repo-prj-my-app",
      source_type: "EXTERNAL_CLONE",
    });
    expect(screen.queryByDisplayValue(TOKEN)).toBeNull();

    await waitFor(() => expect(screen.getByText("CLONING")).toBeTruthy());
    expect(screen.queryByRole("radio", { name: "Register new" })).toBeNull();
    await waitFor(() =>
      expect(callsTo("GET", "/events/stream?project_id=proj-1")).toHaveLength(1),
    );

    setRepoStatus("repo-new", "READY");
    await act(async () => {
      emitEvent(42, "repository.materialized", { repository_id: "repo-new", sha: "abc123" });
    });
    await waitFor(() => expect(screen.getByText("READY")).toBeTruthy());
    await waitFor(() => expect(streamAborted).toBe(true));

    const queries = client.getQueryCache().getAll();
    expect(queries.map((q) => q.queryKey)).toEqual(
      expect.arrayContaining([
        ["repositories", "list", "proj-1"],
        ["repositories", "detail", "repo-new"],
      ]),
    );
    const cacheJson = JSON.stringify([
      queries.map((q) => ({ key: q.queryKey, state: q.state })),
      client.getMutationCache().getAll().map((m) => m.state),
    ]);
    expect(cacheJson).toContain("repo-new");
    expect(cacheJson).not.toContain(TOKEN);
    expect(storageContains(TOKEN)).toBe(false);

    fireEvent.change(inputAfterLabel("Objective"), { target: { value: "Baseline the monolith" } });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Create delivery cycle" })).toHaveProperty(
        "disabled",
        false,
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Create delivery cycle" }));

    await waitFor(() =>
      expect(callsTo("POST", "/projects/proj-1/delivery-cycles")[0]?.body).toEqual({
        type: "BROWNFIELD_ONBOARDING",
        objective: "Baseline the monolith",
        repository_id: "repo-new",
      }),
    );
    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/projects/proj-1/cycles/cycle-bf/studio"),
    );
  });

  it("offers only the existing repository when the project already has one", async () => {
    server.repos = [repository("repo-1", "READY", { name: "legacy" })];
    renderDialog();
    await openBrownfield();

    await waitFor(() => expect(screen.getByText("legacy · GITHUB · READY")).toBeTruthy());
    expect(screen.queryByRole("radio", { name: "Register new" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Register repository" })).toBeNull();
    expect(screen.getByText("A project has one repository.")).toBeTruthy();
  });

  it("disables unsupported providers", async () => {
    renderDialog();
    await openBrownfield();
    await fillRegistration("app", "https://github.com/org/app.git");

    for (const p of ["GITLAB", "BITBUCKET"]) {
      const option = screen.getByRole("option", { name: `${p} (not supported yet)` });
      expect(option).toHaveProperty("disabled", true);
    }
    expect(screen.getByRole("option", { name: "GITHUB" })).toHaveProperty("disabled", false);
  });

  it("retry after a failed registration reuses the stored credential_ref", async () => {
    server.registerErrors = [
      { code: "INVALID_REMOTE_URL", message: "Remote providers require HTTPS remote_url" },
    ];
    renderDialog();
    await openBrownfield();
    await fillRegistration("app", "http://github.com/org/app.git", TOKEN);
    await confirmRegister();

    await waitFor(() =>
      expect(screen.getByText("Remote providers require HTTPS remote_url")).toBeTruthy(),
    );
    expect(callsTo("PUT", "/secrets/repo-prj-app")).toHaveLength(1);
    expect(inputAfterLabel("Access token (optional, sent once)").value).toBe("");
    expect(screen.getByText("credential_ref=secret:repo-prj-app")).toBeTruthy();

    const previewRow = screen.getByRole("button", { name: "Confirm send" }).parentElement!;
    fireEvent.click(within(previewRow).getByRole("button", { name: "Cancel" }));
    fireEvent.change(inputAfterLabel("Remote URL"), {
      target: { value: "https://github.com/org/app.git" },
    });
    await confirmRegister();

    await waitFor(() => expect(callsTo("POST", "/projects/proj-1/repositories")).toHaveLength(2));
    const [first, second] = callsTo("POST", "/projects/proj-1/repositories");
    expect((first.body as { credential_ref: string }).credential_ref).toBe("secret:repo-prj-app");
    expect((second.body as { credential_ref: string }).credential_ref).toBe("secret:repo-prj-app");
    expect(second.headers["Idempotency-Key"]).not.toBe(first.headers["Idempotency-Key"]);
    expect(calls.filter((c) => c.method === "PUT")).toHaveLength(1);
    await waitFor(() => expect(screen.getByText("CLONING")).toBeTruthy());
  });

  it("ERROR shows status_reason, last attempt error and retries materialization", async () => {
    server.repos = [
      repository("repo-1", "ERROR", { status_reason: "Clone failed after 3 attempts" }),
    ];
    server.materializations = [
      {
        id: "m-1",
        kind: "CLONE",
        attempt: 1,
        status: "FAILED",
        resulting_sha: null,
        observed_default_branch: null,
        error_class: "TimeoutError",
        error_detail: "timed out",
        started_at: "2026-10-01T00:00:00Z",
        finished_at: "2026-10-01T00:01:00Z",
      },
      {
        id: "m-2",
        kind: "CLONE",
        attempt: 2,
        status: "FAILED",
        resulting_sha: null,
        observed_default_branch: null,
        error_class: "AuthenticationError",
        error_detail: "remote returned 401",
        started_at: "2026-10-01T00:02:00Z",
        finished_at: "2026-10-01T00:03:00Z",
      },
    ];
    renderDialog();
    await openBrownfield();
    await waitFor(() => expect(screen.getByText("app · GITHUB · ERROR")).toBeTruthy());
    fireEvent.change(inputAfterLabel("Project repository"), { target: { value: "repo-1" } });

    await waitFor(() => expect(screen.getByText("AuthenticationError")).toBeTruthy());
    expect(screen.getByText("Clone failed after 3 attempts")).toBeTruthy();
    expect(screen.getByText("remote returned 401")).toBeTruthy();
    expect(screen.queryByText("TimeoutError")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Retry materialization" }));
    expect(
      screen.getByText(/POST \/repositories\/repo-1\/commands\/retry_materialization/),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Confirm send" }));

    await waitFor(() =>
      expect(
        callsTo("POST", "/repositories/repo-1/commands/retry_materialization"),
      ).toHaveLength(1),
    );
    const [retry] = callsTo("POST", "/repositories/repo-1/commands/retry_materialization");
    expect(retry.headers["Idempotency-Key"]).toBeTruthy();
    await waitFor(() => expect(screen.getByText("CLONING")).toBeTruthy());
  });

  it("polls only while the dialog is open and tracking", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    server.repos = [repository("repo-1", "CLONING")];
    const { setOpen } = renderDialog();
    await openBrownfield();
    await waitFor(() => expect(screen.getByText("app · GITHUB · CLONING")).toBeTruthy());
    fireEvent.change(inputAfterLabel("Project repository"), { target: { value: "repo-1" } });
    await waitFor(() => expect(callsTo("GET", "/repositories/repo-1")).toHaveLength(1));
    await waitFor(() =>
      expect(callsTo("GET", "/events/stream?project_id=proj-1")).toHaveLength(1),
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
    });
    await waitFor(() => expect(callsTo("GET", "/repositories/repo-1")).toHaveLength(2));

    setOpen(false);
    await waitFor(() => expect(streamAborted).toBe(true));
    const listCalls = callsTo("GET", "/projects/proj-1/repositories").length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(callsTo("GET", "/repositories/repo-1")).toHaveLength(2);
    expect(callsTo("GET", "/projects/proj-1/repositories")).toHaveLength(listCalls);
    expect(callsTo("GET", "/events/stream?project_id=proj-1")).toHaveLength(1);
  });

  it("does not fetch project repositories while closed", async () => {
    renderDialog({ open: false });
    await waitFor(() => expect(callsTo("GET", "/actors/me")).toHaveLength(1));
    expect(callsTo("GET", "/projects/proj-1/repositories")).toHaveLength(0);
  });

  it("gates register, retry and create on the OPERATOR role", async () => {
    server.roles = ["APPROVER"];
    server.repos = [repository("repo-1", "ERROR", { status_reason: "boom" })];
    renderDialog();
    await waitFor(() =>
      expect(screen.getByText("You need the OPERATOR role to do this.")).toBeTruthy(),
    );
    await openBrownfield();
    await waitFor(() => expect(screen.getByText("app · GITHUB · ERROR")).toBeTruthy());
    fireEvent.change(inputAfterLabel("Project repository"), { target: { value: "repo-1" } });
    await waitFor(() => expect(screen.getByText("boom")).toBeTruthy());

    expect(screen.getByRole("button", { name: "Retry materialization" })).toHaveProperty(
      "disabled",
      true,
    );
    fireEvent.change(inputAfterLabel("Objective"), { target: { value: "x" } });
    expect(screen.getByRole("button", { name: "Create delivery cycle" })).toHaveProperty(
      "disabled",
      true,
    );
  });

  it("disables Register repository for actors without OPERATOR", async () => {
    server.roles = [];
    renderDialog();
    await openBrownfield();
    await fillRegistration("app", "https://github.com/org/app.git");
    await waitFor(() =>
      expect(screen.getByText("You need the OPERATOR role to do this.")).toBeTruthy(),
    );
    expect(screen.getByRole("button", { name: "Register repository" })).toHaveProperty(
      "disabled",
      true,
    );
  });
});
