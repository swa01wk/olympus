"use client";

import { useProjectOverview } from "@/src/api/hooks/use-olympus-queries";
import { useSearchParams } from "next/navigation";
import { useMemo } from "react";

/** Resolve cycle id from route param or `?cycle=` with project overview fallback. */
export function useResolvedCycleId(projectId: string, routeCycleId?: string): string {
  const searchParams = useSearchParams();
  const fromQuery = searchParams.get("cycle") ?? "";
  const overview = useProjectOverview(projectId);

  return useMemo(() => {
    if (routeCycleId) return routeCycleId;
    if (fromQuery) return fromQuery;
    const active = overview.data?.active_cycle_id as string | undefined;
    return active ?? "";
  }, [routeCycleId, fromQuery, overview.data?.active_cycle_id]);
}
