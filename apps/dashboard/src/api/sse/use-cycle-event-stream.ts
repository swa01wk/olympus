"use client";

import { useEffect, useRef, useState } from "react";
import { connectCycleEventStream, type StreamState } from "@/src/api/sse/cycle-event-stream";

export type CycleStreamSnapshot = {
  state: StreamState;
  lastEventAt: Date | null;
  lastRefreshAt: Date | null;
};

type Options = {
  enabled?: boolean;
  invalidate?: () => void;
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

  useEffect(() => {
    invalidateRef.current = options.invalidate;
  }, [options.invalidate]);

  useEffect(() => {
    if (!active || !cycleId) return;
    const ac = new AbortController();
    void connectCycleEventStream(
      cycleId,
      {
        onStateChange: (state) => setSnapshot((s) => ({ ...s, state })),
        onEvent: () => {
          const now = new Date();
          setSnapshot((s) => ({ ...s, lastEventAt: now, lastRefreshAt: now }));
          invalidateRef.current?.();
        },
      },
      ac.signal,
    ).catch(() => {
      setSnapshot((s) => ({ ...s, state: "disconnected" }));
    });
    return () => ac.abort();
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
