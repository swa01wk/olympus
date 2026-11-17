"use client";

import {
  fetchAutopilot,
  fetchAutopilotActivity,
  fetchHome,
  retryAutopilot,
  setAutopilot,
  startJourney,
} from "@/src/api/autopilot";
import type { AutopilotView, StartJourneyInput } from "@/src/api/types/autopilot";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

/** Fallback refresh while the live event stream is down; the stream refreshes sooner. */
const FALLBACK_POLL_MS = 10_000;

export const autopilotKeys = {
  home: ["home"] as const,
  status: (cycleId: string) => ["autopilot", cycleId] as const,
  activity: (cycleId: string) => ["autopilot", cycleId, "activity"] as const,
};

export function useHome() {
  return useQuery({
    queryKey: autopilotKeys.home,
    queryFn: fetchHome,
    refetchInterval: FALLBACK_POLL_MS,
  });
}

export function useAutopilot(cycleId: string | undefined) {
  return useQuery({
    queryKey: autopilotKeys.status(cycleId ?? ""),
    queryFn: () => fetchAutopilot(cycleId!),
    enabled: Boolean(cycleId),
    refetchInterval: (q) => (q.state.data?.status === "DONE" ? false : FALLBACK_POLL_MS),
  });
}

export function useAutopilotActivity(cycleId: string | undefined) {
  return useQuery({
    queryKey: autopilotKeys.activity(cycleId ?? ""),
    queryFn: () => fetchAutopilotActivity(cycleId!),
    enabled: Boolean(cycleId),
    refetchInterval: FALLBACK_POLL_MS,
  });
}

export function useStartJourney() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ input, key }: { input: StartJourneyInput; key: string }) =>
      startJourney(input, key),
    onSuccess: () => qc.invalidateQueries({ queryKey: autopilotKeys.home }),
  });
}

function useAutopilotMutation(cycleId: string, fn: () => Promise<AutopilotView>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (view) => {
      qc.setQueryData(autopilotKeys.status(cycleId), view);
      void qc.invalidateQueries({ queryKey: ["autopilot", cycleId] });
    },
  });
}

export function useRetryAutopilot(cycleId: string) {
  return useAutopilotMutation(cycleId, () => retryAutopilot(cycleId));
}

export function useToggleAutopilot(cycleId: string, enabled: boolean) {
  return useAutopilotMutation(cycleId, () => setAutopilot(cycleId, enabled));
}
