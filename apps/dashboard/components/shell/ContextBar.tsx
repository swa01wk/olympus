"use client";

import { useQuery } from "@tanstack/react-query";
import { CycleSwitcher } from "./CycleSwitcher";
import { getServices } from "@/lib/api/services";
import { qk } from "@/lib/query/keys";
import { useActiveCycleId, useProjectId } from "@/lib/hooks/use-active-cycle";
import { RepositorySummaryChip } from "@/components/repository/RepositorySummaryChip";
import { LiveConnectionIndicator } from "./LiveConnectionIndicator";

export function ContextBar() {
  const projectId = useProjectId();
  const cycleId = useActiveCycleId(projectId);

  const projectQ = useQuery({
    queryKey: qk.project(projectId ?? ""),
    queryFn: async () => (await getServices()).projects.get(projectId!),
    enabled: !!projectId,
  });
  const cycleQ = useQuery({
    queryKey: qk.cycle(cycleId ?? ""),
    queryFn: async () => (await getServices()).deliveryCycles.get(cycleId!),
    enabled: !!cycleId,
  });

  if (!projectId) return null;

  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] bg-[var(--raised)] px-4 py-2">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span
          className="font-mono text-amber-300"
          data-testid="project-context"
          data-key={projectQ.data?.key}
        >
          {projectQ.data?.key}
        </span>
        <span className="text-[var(--muted)]">{projectQ.data?.name}</span>
        {cycleQ.data && (
          <>
            <span
              className="rounded border border-[var(--border)] px-2 py-0.5 text-xs font-mono"
              data-testid="delivery-cycle-context"
              data-key={cycleQ.data.key}
            >
              {cycleQ.data.key}
            </span>
            <span
              className="rounded border border-[var(--border)] px-2 py-0.5 text-xs"
              data-testid="journey-context"
              data-type={cycleQ.data.type}
            >
              {cycleQ.data.type.replace(/_/g, " ")}
            </span>
          </>
        )}
        <RepositorySummaryChip projectId={projectId} />
        <LiveConnectionIndicator />
      </div>
      <CycleSwitcher projectId={projectId} />
    </header>
  );
}
