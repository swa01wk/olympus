"use client";

import { useEffect, useRef, useState } from "react";
import type { DomainEventPayload } from "@/src/api/types/core";
import { connectCycleEventStream, type StreamState } from "@/src/api/sse/cycle-event-stream";

export type CycleStreamSnapshot = {
  state: StreamState;
  lastEventAt: Date | null;
  lastRefreshAt: Date | null;
};

type Options = {
  enabled?: boolean;
  invalidate?: () => void;
  onEvent?: (event: DomainEventPayload) => void;
};

/**
 * Workers emit events in bursts (dozens per decompose); each invalidate refetches every active
 * cycle query, so per-event invalidation trips the control API's per-token rate limit.
 */
export const INVALIDATE_THROTTLE_MS = 2_000;

export function useCycleEventStream(cycleId: string | undefined, options: Options = {}) {
  const enabled = options.enabled ?? Boolean(cycleId);
  const active = enabled && Boolean(cycleId);
  const [snapshot, setSnapshot] = useState<CycleStreamSnapshot>({
    state: "disconnected",
    lastEventAt: null,
    lastRefreshAt: null,
  });
  const invalidateRef = useRef(options.invalidate);
  const onEventRef = useRef(options.onEvent);
  const lastEventIdRef = useRef<string | null>(null);

  useEffect(() => {
    invalidateRef.current = options.invalidate;
  }, [options.invalidate]);

  useEffect(() => {
    onEventRef.current = options.onEvent;
  }, [options.onEvent]);

  useEffect(() => {
    if (!active || !cycleId) return;
    let cancelled = false;
    const ac = new AbortController();
    let lastFlushAt = 0;
    let trailingTimer: ReturnType<typeof setTimeout> | null = null;

    const flushInvalidate = () => {
      trailingTimer = null;
      if (cancelled) return;
      lastFlushAt = Date.now();
      setSnapshot((s) => ({ ...s, lastRefreshAt: new Date(lastFlushAt) }));
      invalidateRef.current?.();
    };

    const scheduleInvalidate = () => {
      if (trailingTimer) return;
      const wait = lastFlushAt + INVALIDATE_THROTTLE_MS - Date.now();
      if (wait <= 0) flushInvalidate();
      else trailingTimer = setTimeout(flushInvalidate, wait);
    };

    const run = async () => {
      while (!cancelled && !ac.signal.aborted) {
        try {
          await connectCycleEventStream(
            cycleId,
            {
              onStateChange: (state) => {
                if (!cancelled) setSnapshot((s) => ({ ...s, state }));
              },
              onLastEventId: (sequence) => {
                lastEventIdRef.current = sequence;
              },
              onEvent: (event) => {
                setSnapshot((s) => ({ ...s, lastEventAt: new Date() }));
                scheduleInvalidate();
                onEventRef.current?.(event);
              },
            },
            ac.signal,
            { lastEventId: lastEventIdRef.current },
          );
        } catch {
          if (!cancelled) setSnapshot((s) => ({ ...s, state: "disconnected" }));
        }
        if (cancelled || ac.signal.aborted) break;
        await new Promise((r) => setTimeout(r, 500));
      }
    };

    void run();
    return () => {
      cancelled = true;
      ac.abort();
      if (trailingTimer) clearTimeout(trailingTimer);
    };
  }, [cycleId, active]);

  if (!active) {
    return {
      state: "disconnected" as const,
      lastEventAt: snapshot.lastEventAt,
      lastRefreshAt: snapshot.lastRefreshAt,
    };
  }

  return snapshot;
}

/** SSE invalidation for a cycle — pair with data hooks on S02. */
export function useCycleLiveUpdates(cycleId: string | undefined, invalidate: () => void) {
  return useCycleEventStream(cycleId, { invalidate });
}
