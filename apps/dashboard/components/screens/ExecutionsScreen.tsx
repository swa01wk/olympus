"use client";

import { CycleDrillFrame } from "@/components/cycle/CycleDrillFrame";
import { ExecutionTimeline } from "@/components/executions/ExecutionTimeline";
import { EmptyState, Panel } from "@/components/primitives";
import { useResolvedCycleId } from "@/lib/cycle-context";
import { useAgentActivity } from "@/src/api/hooks/use-drill-queries";
import { useExecutionsForTasks, useTasks } from "@/src/api/hooks/use-olympus-queries";
import type { Execution } from "@/src/api/types/core";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo } from "react";

export function ExecutionsScreen({ projectId }: { projectId: string }) {
  const router = useRouter();
  const cycleId = useResolvedCycleId(projectId);
  const tasks = useTasks(cycleId || undefined);
  const taskIds = useMemo(() => (tasks.data ?? []).map((t) => t.id), [tasks.data]);
  const execQueries = useExecutionsForTasks(taskIds);
  const activity = useAgentActivity(projectId);

  const executions = useMemo(() => {
    const all: Execution[] = [];
    for (const q of execQueries) {
      if (q.data) all.push(...q.data);
    }
    return all.sort((a, b) => b.attempt_number - a.attempt_number);
  }, [execQueries]);

  return (
    <CycleDrillFrame projectId={projectId} cycleId={cycleId} activeScreen="S05">
      <Panel title="S05 · Executions" sub="All attempts in this cycle (failures and stale kept)">
        {executions.length === 0 && !tasks.isLoading && (
          <EmptyState title="No executions" description="Tasks have not been attempted yet." />
        )}
        <ExecutionTimeline
          executions={executions}
          selectedId={undefined}
          onSelect={(id) => router.push(`/executions/${id}`)}
        />
        {executions.map((ex) => (
          <p key={ex.id} className="text-sm">
            <Link className="ol-idlink" href={`/executions/${ex.id}`}>
              {ex.key}
            </Link>{" "}
            — attempt {ex.attempt_number}
          </p>
        ))}
      </Panel>
      {activity.data && (
        <Panel title="Agent activity" sub="Project-wide execution context">
          <pre className="text-xs overflow-auto max-h-40">{JSON.stringify(activity.data, null, 2)}</pre>
        </Panel>
      )}
    </CycleDrillFrame>
  );
}
