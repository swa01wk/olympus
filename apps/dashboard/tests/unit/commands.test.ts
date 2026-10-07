import { afterEach, describe, expect, it, vi } from "vitest";
import { sendDeliveryCycleCommand } from "@/src/api/commands";

describe("sendCommand", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("POSTs expected_state and Idempotency-Key", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ ok: true }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await sendDeliveryCycleCommand("cycle-1", "start_planning", "ARCHITECTURE", null, "idem-1");

    expect(fetchMock).toHaveBeenCalledOnce();
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBe("idem-1");
    expect(JSON.parse(init.body as string)).toEqual({
      expected_state: "ARCHITECTURE",
      payload: null,
    });
  });
});
