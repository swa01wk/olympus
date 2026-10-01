"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { StatusBadge } from "@/components/status/StatusBadge";
import { getServices } from "@/lib/api/services";
import { useActiveCycleId } from "@/lib/hooks/use-active-cycle";
import { qk } from "@/lib/query/keys";
import { isExecutionActive } from "@/lib/utils/execution-active";

export default function ExecutionsListPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const cycleId = useActiveCycleId(projectId);

  const execQ = useQuery({
    queryKey: qk.cycleExecutions(cycleId ?? ""),
    queryFn: async () => (await getServices()).executions.listByCycle(cycleId!),
    enabled: !!cycleId,
  });

  const tasksQ = useQuery({
    queryKey: qk.cycleTasks(cycleId ?? ""),
    queryFn: async () => (await getServices()).tasks.listByCycle(cycleId!),
    enabled: !!cycleId,
  });

  const taskKey = new Map(tasksQ.data?.map((t) => [t.id, t.key]));

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Executions</h1>
      {!cycleId && <p className="text-sm text-[var(--muted)]">Loading cycle context…</p>}
      {cycleId && (
      <Panel title="Cycle executions" stateRail="running" actions={<FixtureBadge />}>
        <ul className="space-y-2">
          {execQ.data?.map((e) => (
            <li key={e.id} className="flex flex-wrap items-center gap-2 rounded border border-[var(--border)] p-2">
              <Link href={`/executions/${e.id}`} className="font-mono text-sky-300 hover:underline">
                {e.key}
              </Link>
              <StatusBadge value={e.status} kind="execution" />
              <span className="text-xs text-[var(--muted)]">task {taskKey.get(e.task_id)}</span>
              {e.previous_execution_id && (
                <span className="text-[10px] text-orange-300">
                  retry after {e.previous_execution_id.slice(0, 8)}
                </span>
              )}
              {isExecutionActive(e.status) && <span className="text-sky-400">active</span>}
            </li>
          ))}
        </ul>
      </Panel>
      )}
    </div>
  );
}
