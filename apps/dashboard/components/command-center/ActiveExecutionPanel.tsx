"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Panel } from "@/components/design/Panel";
import { Duration } from "@/components/design/Duration";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { StatusBadge } from "@/components/status/StatusBadge";
import { getServices } from "@/lib/api/services";
import type { Execution, Task, TaskContract } from "@/lib/contracts/entity-types";
import { isExecutionActive } from "@/lib/utils/execution-active";

function pickPrimary(active: Execution[]): Execution | undefined {
  return active.sort((a, b) => (a.started_at ?? "").localeCompare(b.started_at ?? "")).at(-1);
}

export function ActiveExecutionPanel({
  executions,
  tasks,
  contractsByTask,
}: {
  executions: Execution[];
  tasks: Task[];
  contractsByTask: Record<string, TaskContract | undefined>;
}) {
  const active = executions.filter((e) => isExecutionActive(e.status));
  const ex = pickPrimary(active);
  const task = ex ? tasks.find((t) => t.id === ex.task_id) : undefined;
  const contract = ex ? contractsByTask[ex.task_id] : undefined;

  const snapshotQ = useQuery({
    queryKey: ["executionSnapshot", ex?.id],
    queryFn: async () => (await getServices()).executions.snapshot(ex!.id),
    enabled: !!ex,
  });
  const worktreeQ = useQuery({
    queryKey: ["executionWorktree", ex?.id],
    queryFn: async () => (await getServices()).executions.worktree(ex!.id),
    enabled: !!ex,
  });
  const actionsQ = useQuery({
    queryKey: ["executionActions", ex?.id],
    queryFn: async () => (await getServices()).executions.actions(ex!.id),
    enabled: !!ex,
  });

  const actions = actionsQ.data ?? [];
  const latestAction = [...actions].sort((a, b) => (b.requested_at ?? "").localeCompare(a.requested_at ?? ""))[0];
  const derivedPath =
    latestAction?.params && typeof latestAction.params === "object" && "path" in latestAction.params
      ? String((latestAction.params as { path?: string }).path)
      : null;

  return (
    <Panel title="Active Execution" stateRail={ex ? "running" : "neutral"} actions={<FixtureBadge />}>
      {!ex ? (
        <p className="text-xs text-[var(--muted)]">No active execution on this cycle.</p>
      ) : (
        <div className="space-y-2 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <Link href={`/executions/${ex.id}`} className="font-mono text-lg text-sky-300 hover:underline">
              {ex.key}
            </Link>
            <StatusBadge value={ex.status} kind="execution" />
            {ex.started_at && <Duration startedAt={ex.started_at} />}
          </div>
          <dl className="grid gap-1 md:grid-cols-2">
            <Row label="Task" value={task?.key ?? ex.task_id} />
            <Row
              label="TaskContract"
              value={contract ? `${contract.key}:v${contract.version}` : "—"}
            />
            <Row label="Runtime" value="LangGraphRuntime (M-27, non-authoritative)" />
            <Row label="Agent profile" value={ex.agent_profile ?? "—"} />
            <Row label="Model alias" value={contract?.body.model_alias ?? "—"} />
            <Row label="Snapshot" value={snapshotQ.data?.snapshot_hash?.slice(0, 12) ?? "—"} />
            <Row label="Base SHA" value={snapshotQ.data?.base_commit?.slice(0, 12) ?? "—"} />
            <Row label="Worktree" value={worktreeQ.data ? `${worktreeQ.data.path} (${worktreeQ.data.mode})` : "—"} />
            <Row label="Current action" value={latestAction ? `${latestAction.tool} ${latestAction.status}` : "—"} />
            <Row label="Current file (derived)" value={derivedPath ?? "—"} />
          </dl>
        </div>
      )}
    </Panel>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <dt className="shrink-0 text-[var(--muted)]">{label}</dt>
      <dd className="truncate font-mono">{value}</dd>
    </div>
  );
}
