import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useOrchestratorChat } from "@/src/api/hooks/use-orchestrator-chat";
import { clearStoredSession, writeStoredSession } from "@/lib/chat-transcript";

const POLL_MS = 2000;

describe("useOrchestratorChat", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("reuses session from sessionStorage until expired", async () => {
    writeStoredSession("cycle-1", {
      sessionId: "sess-stored",
      expiresAt: new Date(Date.now() + 3600_000).toISOString(),
    });
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      text: async () =>
        JSON.stringify({
          id: "sess-stored",
          project_id: "p1",
          delivery_cycle_id: "cycle-1",
          expires_at: new Date(Date.now() + 3600_000).toISOString(),
          turns: [{ role: "user", text: "Hi" }],
        }),
    } as Response);

    const { result } = renderHook(() => useOrchestratorChat("p1", "cycle-1"));

    await waitFor(() => expect(result.current.sessionId).toBe("sess-stored"));
    expect(fetchMock).toHaveBeenCalled();
    expect(fetchMock.mock.calls[0][0]).toContain("/orchestrator/sessions/sess-stored");
    expect(createSessionCalls(fetchMock)).toBe(0);
  });

  it("creates new session when stored session expired", async () => {
    writeStoredSession("cycle-1", {
      sessionId: "sess-old",
      expiresAt: new Date(Date.now() - 1000).toISOString(),
    });
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      text: async () =>
        JSON.stringify({
          id: "sess-new",
          project_id: "p1",
          delivery_cycle_id: "cycle-1",
          expires_at: new Date(Date.now() + 3600_000).toISOString(),
          turns: [],
        }),
    } as Response);

    const { result } = renderHook(() => useOrchestratorChat("p1", "cycle-1"));
    await waitFor(() => expect(result.current.sessionId).toBe("sess-new"));
    expect(createSessionCalls(fetchMock)).toBeGreaterThan(0);
    clearStoredSession("cycle-1");
  });

  it("sends studio focus on postTurn when provided", async () => {
    writeStoredSession("cycle-1", {
      sessionId: "sess-1",
      expiresAt: new Date(Date.now() + 3600_000).toISOString(),
    });
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.includes("/turns") && init?.method === "POST") {
        const body = JSON.parse(init.body as string) as Record<string, unknown>;
        expect(body.focus).toEqual({
          subject_type: "architecture",
          subject_id: "arch-9",
        });
        return {
          ok: true,
          status: 200,
          text: async () => JSON.stringify({ execution_id: "ex-focus" }),
        } as Response;
      }
      return {
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({
            id: "sess-1",
            project_id: "p1",
            delivery_cycle_id: "cycle-1",
            expires_at: new Date(Date.now() + 3600_000).toISOString(),
            turns: [],
          }),
      } as Response;
    });

    const { result } = renderHook(() =>
      useOrchestratorChat("p1", "cycle-1", {
        subject_type: "architecture",
        subject_id: "arch-9",
      }),
    );
    await waitFor(() => expect(result.current.sessionId).toBe("sess-1"));
    await act(async () => {
      await result.current.send("Review this architecture");
    });
  });

  it("resolves pending via onTurnCompleted", async () => {
    writeStoredSession("cycle-1", {
      sessionId: "sess-1",
      expiresAt: new Date(Date.now() + 3600_000).toISOString(),
    });
    const fetchMock = vi.mocked(fetch);
    let sessionReads = 0;
    fetchMock.mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.includes("/turns") && init?.method === "POST") {
        return {
          ok: true,
          status: 200,
          text: async () => JSON.stringify({ execution_id: "ex-99" }),
        } as Response;
      }
      sessionReads += 1;
      const turns =
        sessionReads > 2
          ? [
              { role: "user", text: "Hello" },
              { role: "assistant", text: "Done", intent: "EXPLAIN", execution_id: "ex-99" },
            ]
          : [{ role: "user", text: "Hello" }];
      return {
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({
            id: "sess-1",
            project_id: "p1",
            delivery_cycle_id: "cycle-1",
            expires_at: new Date(Date.now() + 3600_000).toISOString(),
            turns,
          }),
      } as Response;
    });

    const { result } = renderHook(() => useOrchestratorChat("p1", "cycle-1"));
    await waitFor(() => expect(result.current.sessionId).toBe("sess-1"));

    await act(async () => {
      await result.current.send("Hello");
    });
    expect(result.current.lines.some((l) => l.kind === "pending")).toBe(true);

    await act(async () => {
      result.current.onTurnCompleted({ execution_id: "ex-99" });
    });

    await waitFor(() =>
      expect(result.current.lines.some((l) => l.kind === "assistant")).toBe(true),
    );
    expect(result.current.lines.some((l) => l.kind === "pending")).toBe(false);
  });

  it("resolves pending via polling fallback", async () => {
    vi.useFakeTimers();
    writeStoredSession("cycle-1", {
      sessionId: "sess-1",
      expiresAt: new Date(Date.now() + 3600_000).toISOString(),
    });
    const fetchMock = vi.mocked(fetch);
    let pollReads = 0;
    fetchMock.mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.includes("/turns") && init?.method === "POST") {
        return {
          ok: true,
          status: 200,
          text: async () => JSON.stringify({ execution_id: "ex-poll" }),
        } as Response;
      }
      pollReads += 1;
      const turns =
        pollReads >= 4
          ? [
              { role: "user", text: "Ping" },
              { role: "assistant", text: "Reply", intent: "EXPLAIN" },
            ]
          : [{ role: "user", text: "Ping" }];
      return {
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({
            id: "sess-1",
            turns,
            expires_at: new Date(Date.now() + 3600_000).toISOString(),
          }),
      } as Response;
    });

    const { result } = renderHook(() => useOrchestratorChat("p1", "cycle-1"));
    await act(async () => {
      await Promise.resolve();
    });

    await act(async () => {
      await result.current.send("Ping");
    });

    await act(async () => {
      for (let i = 0; i < 4; i++) {
        await vi.advanceTimersByTimeAsync(POLL_MS + 100);
        await Promise.resolve();
      }
    });

    expect(result.current.lines.some((l) => l.kind === "assistant")).toBe(true);
    expect(result.current.lines.some((l) => l.kind === "pending")).toBe(false);
  });
});

function createSessionCalls(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls.filter(
    (c) => String(c[0]).includes("/orchestrator/sessions") && c[1]?.method === "POST",
  ).length;
}
