"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getDataMode } from "@/lib/config/data-mode";
import { useActiveCycleId, useProjectId } from "@/lib/hooks/use-active-cycle";
import { invalidateForEvent } from "./invalidation-map";

type StreamStatus = "OFFLINE" | "CONNECTING" | "LIVE" | "RECONNECTING" | "POLLING";

const StreamCtx = createContext<StreamStatus>("OFFLINE");

export function useEventStreamStatus() {
  return useContext(StreamCtx);
}

export function EventStreamProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<StreamStatus>("OFFLINE");
  const qc = useQueryClient();
  const projectId = useProjectId();
  const cycleId = useActiveCycleId(projectId);

  useEffect(() => {
    if (getDataMode() !== "fixture" || !cycleId) {
      const t = window.setTimeout(() => setStatus("POLLING"), 0);
      return () => window.clearTimeout(t);
    }
    let cancelled = false;
    const connectTimer = window.setTimeout(() => setStatus("CONNECTING"), 0);
    void import("./fixture-stream").then(({ startFixtureStream, stopFixtureStream }) => {
      if (cancelled) return;
      startFixtureStream(cycleId, (ev) => {
        invalidateForEvent(qc, ev.event_type, ev.delivery_cycle_id ?? undefined);
        setStatus("LIVE");
      });
      setStatus("LIVE");
      return () => stopFixtureStream();
    });
    return () => {
      window.clearTimeout(connectTimer);
      cancelled = true;
      void import("./fixture-stream").then(({ stopFixtureStream }) => stopFixtureStream());
    };
  }, [cycleId, qc]);

  return <StreamCtx.Provider value={status}>{children}</StreamCtx.Provider>;
}
