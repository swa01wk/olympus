import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DomainEventPayload } from "@/src/api/types/core";

type Handlers = { onEvent: (event: DomainEventPayload) => void };

let emit: ((event: DomainEventPayload) => void) | null = null;

vi.mock("@/src/api/sse/cycle-event-stream", () => ({
  connectCycleEventStream: (_cycleId: string, handlers: Handlers, signal: AbortSignal) => {
    emit = handlers.onEvent;
    return new Promise<void>((resolve) => signal.addEventListener("abort", () => resolve()));
  },
}));

const { INVALIDATE_THROTTLE_MS, useCycleEventStream } = await import(
  "@/src/api/sse/use-cycle-event-stream"
);

function event(i: number): DomainEventPayload {
  return { id: `e${i}`, sequence: i, event_type: "task.transitioned", payload: {} } as DomainEventPayload;
}

describe("useCycleEventStream", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    emit = null;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("coalesces invalidation across an event burst but forwards every event", async () => {
    const invalidate = vi.fn();
    const onEvent = vi.fn();
    const { unmount } = renderHook(() => useCycleEventStream("cycle-1", { invalidate, onEvent }));
    await act(async () => {});
    expect(emit).not.toBeNull();

    act(() => {
      for (let i = 0; i < 50; i += 1) emit!(event(i));
    });
    expect(onEvent).toHaveBeenCalledTimes(50);
    expect(invalidate).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(INVALIDATE_THROTTLE_MS);
    });
    expect(invalidate).toHaveBeenCalledTimes(2);

    await act(async () => {
      vi.advanceTimersByTime(INVALIDATE_THROTTLE_MS * 5);
    });
    expect(invalidate).toHaveBeenCalledTimes(2);

    unmount();
  });

  it("drops a pending trailing invalidate on unmount", async () => {
    const invalidate = vi.fn();
    const { unmount } = renderHook(() => useCycleEventStream("cycle-1", { invalidate }));
    await act(async () => {});

    act(() => {
      emit!(event(1));
      emit!(event(2));
    });
    expect(invalidate).toHaveBeenCalledTimes(1);

    unmount();
    vi.advanceTimersByTime(INVALIDATE_THROTTLE_MS * 2);
    expect(invalidate).toHaveBeenCalledTimes(1);
  });
});
