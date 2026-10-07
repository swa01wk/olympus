"use client";

import { ExecutionEventList } from "@/components/executions/ExecutionTimeline";
import { AppShell } from "@/components/shell/AppShell";
import { EmptyState, KV, Panel, StatusBadge } from "@/components/primitives";
import {
  useExecutionDetail,
  useExecutionEvents,
} from "@/src/api/hooks/use-drill-queries";
import { useTask } from "@/src/api/hooks/use-drill-queries";
import { useDeliveryCycle, useDeliveryCycles, useProject } from "@/src/api/hooks/use-olympus-queries";
import Link from "next/link";

export function ExecutionDetailScreen({ executionId }: { executionId: string }) {
  const ex = useExecutionDetail(executionId);
  const events = useExecutionEvents(executionId);
  const taskId = ex.data?.task_id;
  const task = useTask(taskId);
  const cycleIdFromTask = task.data?.delivery_cycle_id;

  const cycle = useDeliveryCycle(cycleIdFromTask);
  const projectId = cycle.data?.project_id;
  const project = useProject(projectId);
  const cycles = useDeliveryCycles(projectId);

  if (ex.isLoading) {
    return <p className="ol-muted p-8">Loading execution…</p>;
  }

  if (!ex.data) {
    return <EmptyState title="Execution not found" description="Check the execution id." />;
  }

  return (
    <AppShell
      project={project.data}
      cycles={cycles.data ?? []}
      cycleId={cycleIdFromTask ?? ""}
      onCycleChange={() => {}}
      stream={{ state: "disconnected", lastEventAt: null, lastRefreshAt: null }}
    >
      <div className="ol-screen">
        <h1 className="ol-title">S05 · Execution inspector</h1>
        {projectId && cycleIdFromTask && (
          <Link className="ol-idlink text-sm" href={`/projects/${projectId}/executions?cycle=${cycleIdFromTask}`}>
            ← All attempts in cycle
          </Link>
        )}
        <Panel title={ex.data.key} sub={`Attempt ${ex.data.attempt_number} · ${ex.data.executor_kind}`}>
          <StatusBadge status={ex.data.status} />
          <KV
            rows={(() => {
              const rows: [string, string][] = [["Task", ex.data.task_id]];
              if (ex.data.snapshot_hash) rows.push(["Snapshot hash", ex.data.snapshot_hash]);
              if (ex.data.failure_class) rows.push(["Failure class", ex.data.failure_class]);
              return rows;
            })()}
          />
        </Panel>
        <Panel title="Governed tool events" sub="ToolGateway decisions per event">
          {events.isLoading && <p className="text-sm ol-muted">Loading events…</p>}
          <ExecutionEventList events={events.data ?? []} />
        </Panel>
      </div>
    </AppShell>
  );
}
