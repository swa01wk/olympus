import { afterEach, describe, expect, it, vi } from "vitest";
import {
  connectCycleEventStream,
  parseCycleSseBlock,
} from "@/src/api/sse/cycle-event-stream";

describe("cycle-event-stream", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("parses id lines into event sequence", () => {
    const block = [
      "id: 42",
      "event: orchestrator.turn_completed",
      'data: {"id":"evt-1","sequence":0,"event_type":"orchestrator.turn_completed","payload":{}}',
    ].join("\n");
    const evt = parseCycleSseBlock(block);
    expect(evt?.sequence).toBe(42);
    expect(evt?.event_type).toBe("orchestrator.turn_completed");
  });

  it("sends Last-Event-ID on reconnect after id lines were parsed", async () => {
    const fetchMock = vi.fn();
    let call = 0;
    fetchMock.mockImplementation(async () => {
      call += 1;
      if (call === 1) {
        const encoder = new TextEncoder();
        const chunk = encoder.encode(
          [
            "id: 7",
            "event: delivery_cycle.transitioned",
            'data: {"id":"e1","sequence":7,"event_type":"delivery_cycle.transitioned","payload":{}}',
            "",
            "",
          ].join("\n"),
        );
        let reads = 0;
        return {
          ok: true,
          body: {
            getReader: () => ({
              read: async () => {
                if (reads === 0) {
                  reads += 1;
                  return { done: false, value: chunk };
                }
                return { done: true, value: undefined };
              },
            }),
          },
        };
      }
      return { ok: false, status: 500, body: null };
    });
    vi.stubGlobal("fetch", fetchMock);

    let lastId: string | null = null;
    const ac = new AbortController();
    await connectCycleEventStream(
      "cycle-abc",
      {
        onLastEventId: (sequence) => {
          lastId = sequence;
        },
        onEvent: () => {},
      },
      ac.signal,
    );

    expect(lastId).toBe("7");

    ac.abort();
    await connectCycleEventStream(
      "cycle-abc",
      { onEvent: () => {} },
      ac.signal,
      { lastEventId: lastId },
    );

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [, init2] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect((init2.headers as Record<string, string>)["Last-Event-ID"]).toBe("7");
  });
});
