"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { TaskDag } from "@/components/dag/TaskDag";
import { TaskInspector } from "@/components/dag/TaskInspector";
import { StatusBadge } from "@/components/status/StatusBadge";
import { getServices } from "@/lib/api/services";
import { qk } from "@/lib/query/keys";
import { isExecutionActive } from "@/lib/utils/execution-active";

export default function TaskDagPage() {
  const { projectId, cycleId } = useParams<{ projectId: string; cycleId: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const taskId = search.get("task");
  const tab = search.get("tab") ?? "overview";

  const dagQ = useQuery({
    queryKey: qk.taskDag(cycleId ?? ""),
    queryFn: async () => (await getServices()).tasks.dag(cycleId!),
    enabled: !!cycleId,
  });

  const execQ = useQuery({
    queryKey: qk.cycleExecutions(cycleId ?? ""),
    queryFn: async () => (await getServices()).executions.listByCycle(cycleId!),
    enabled: !!cycleId,
  });

  const execKeyByTask: Record<string, string | undefined> = {};
  execQ.data?.forEach((e) => {
    if (isExecutionActive(e.status) || e.status === "COMPLETED") {
      if (!execKeyByTask[e.task_id]) execKeyByTask[e.task_id] = e.key;
    }
  });

  const selected = dagQ.data?.nodes.find((t) => t.id === taskId);

  const setTask = (id: string, nextTab = tab) => {
    router.push(
      `/projects/${projectId}/cycles/${cycleId}/tasks?cycle=${cycleId}&task=${id}&tab=${nextTab}`,
    );
  };

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Task DAG</h1>
      {dagQ.data && (
        <TaskDag
          tasks={dagQ.data.nodes}
          edges={dagQ.data.edges}
          executionKeyByTaskId={execKeyByTask}
          selectedTaskId={taskId}
          onSelectTask={(id) => setTask(id)}
        />
      )}
      <p className="mb-4 mt-4 text-xs text-[var(--muted)]">List twin (L) — keyboard: select row to inspect.</p>
      <ul className="space-y-2" role="list">
        {dagQ.data?.nodes.map((t) => (
          <li key={t.id} className="rounded border border-[var(--border)] p-3">
            <button type="button" className="w-full text-left" onClick={() => setTask(t.id)}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-amber-300">{t.key}</span>
                <StatusBadge value={t.status} kind="task" />
                <span>{t.title}</span>
              </div>
            </button>
            <Link
              href={`/projects/${projectId}/cycles/${cycleId}/tasks?cycle=${cycleId}&task=${t.id}`}
              className="text-xs text-sky-400"
            >
              Inspect
            </Link>
          </li>
        ))}
      </ul>
      {selected && (
        <TaskInspector
          task={selected}
          projectId={projectId}
          cycleId={cycleId}
          tab={tab}
          onTabChange={(t) => setTask(selected.id, t)}
        />
      )}
    </div>
  );
}
