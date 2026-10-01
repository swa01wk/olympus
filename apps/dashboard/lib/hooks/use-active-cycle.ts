"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "next/navigation";
import { getServices } from "@/lib/api/services";
import { qk } from "@/lib/query/keys";

/** Selected cycle: ?cycle= UUID, else project summary active_cycle_id, else first non-terminal cycle. */
export function useActiveCycleId(projectId: string | undefined) {
  const search = useSearchParams();
  const fromUrl = search.get("cycle");

  const summaryQ = useQuery({
    queryKey: [...qk.project(projectId ?? ""), "summary"],
    queryFn: async () => (await getServices()).projects.summary(projectId!),
    enabled: !!projectId,
  });

  const cyclesQ = useQuery({
    queryKey: qk.cycles(projectId ?? ""),
    queryFn: async () => (await getServices()).deliveryCycles.list(projectId!),
    enabled: !!projectId,
  });

  if (fromUrl) return fromUrl;
  if (summaryQ.data?.active_cycle_id) return summaryQ.data.active_cycle_id;
  const cycles = cyclesQ.data ?? [];
  const active =
    cycles.find((c) => !["COMPLETE", "READY", "CANCELLED", "FAILED"].includes(c.state)) ??
    cycles[0];
  return active?.id ?? null;
}

export function useProjectId() {
  const params = useParams<{ projectId?: string }>();
  return params.projectId;
}
