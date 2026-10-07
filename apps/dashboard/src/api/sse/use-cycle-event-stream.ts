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
                const now = new Date();
                setSnapshot((s) => ({ ...s, lastEventAt: now, lastRefreshAt: now }));
                invalidateRef.current?.();
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
