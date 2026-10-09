"use client";

import { useEffect, useRef } from "react";
import type { DomainEventPayload } from "@/src/api/types/core";
import { connectEventStream } from "@/src/api/sse/cycle-event-stream";

const RECONNECT_MS = 1_000;

/** Project-wide `GET /events/stream?project_id=` — carries events with no cycle id (e.g. `repository.*`). */
export function useProjectEventStream(
  projectId: string | undefined,
  options: { enabled?: boolean; onEvent: (event: DomainEventPayload) => void },
) {
  const active = (options.enabled ?? true) && Boolean(projectId);
  const onEventRef = useRef(options.onEvent);

  useEffect(() => {
    onEventRef.current = options.onEvent;
  }, [options.onEvent]);

  useEffect(() => {
    if (!active || !projectId) return;
    let cancelled = false;
    const ac = new AbortController();
    let lastEventId: string | null = null;
    const path = `/events/stream?${new URLSearchParams({ project_id: projectId })}`;

    const run = async () => {
      while (!cancelled && !ac.signal.aborted) {
        try {
          await connectEventStream(
            path,
            {
              onLastEventId: (sequence) => {
                lastEventId = sequence;
              },
              onEvent: (event) => onEventRef.current(event),
            },
            ac.signal,
            { lastEventId },
          );
        } catch {
          // reconnect below
        }
        if (cancelled || ac.signal.aborted) break;
        await new Promise((r) => setTimeout(r, RECONNECT_MS));
      }
    };

    void run();
    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [projectId, active]);
}
