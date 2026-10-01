"use client";

import { useQuery } from "@tanstack/react-query";
import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { StatusBadge } from "@/components/status/StatusBadge";
import { ExecutionChain } from "@/components/execution/ExecutionChain";
import { getServices } from "@/lib/api/services";
import type { Execution } from "@/lib/contracts/entity-types";

export function ExecutionWorkspace({ execution }: { execution: Execution }) {
  const taskQ = useQuery({
    queryKey: ["task", execution.task_id],
    queryFn: async () => (await getServices()).tasks.get(execution.task_id),
  });
  const contractQ = useQuery({
    queryKey: ["contract", execution.task_id],
    queryFn: async () => (await getServices()).tasks.contract(execution.task_id),
  });
  const snapshotQ = useQuery({
    queryKey: ["executionSnapshot", execution.id],
    queryFn: async () => (await getServices()).executions.snapshot(execution.id),
  });
  const worktreeQ = useQuery({
    queryKey: ["executionWorktree", execution.id],
    queryFn: async () => (await getServices()).executions.worktree(execution.id),
  });
  const commitQ = useQuery({
    queryKey: ["candidateCommit", execution.id],
    queryFn: async () => (await getServices()).executions.candidateCommit(execution.id),
  });
  const actionsQ = useQuery({
    queryKey: ["executionActions", execution.id],
    queryFn: async () => (await getServices()).executions.actions(execution.id),
  });
  const siblingsQ = useQuery({
    queryKey: [...["task", execution.task_id], "executions"],
    queryFn: async () => (await getServices()).executions.listByTask(execution.task_id),
  });

  const siblings = siblingsQ.data?.filter((e) => e.id !== execution.id) ?? [];

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="font-mono text-xl font-semibold">{execution.key}</h1>
        <StatusBadge value={execution.status} kind="execution" />
        <FixtureBadge />
      </header>

      <ExecutionChain task={taskQ.data} contract={contractQ.data} execution={execution} />

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Snapshot" stateRail="neutral" actions={<FixtureBadge />}>
          <dl className="font-mono text-xs">
            <Row label="hash" value={snapshotQ.data?.snapshot_hash ?? "—"} />
            <Row label="base_commit" value={snapshotQ.data?.base_commit ?? "—"} />
          </dl>
        </Panel>
        <Panel title="Worktree" stateRail="neutral" actions={<FixtureBadge />}>
          {worktreeQ.data ? (
            <dl className="font-mono text-xs">
              <Row label="location" value={worktreeQ.data.logical_location ?? worktreeQ.data.path ?? "—"} />
              <Row label="branch" value={worktreeQ.data.branch} />
              <Row label="mode" value={worktreeQ.data.mode} />
              <Row label="status" value={worktreeQ.data.status} />
            </dl>
          ) : (
            <p className="text-xs text-[var(--muted)]">No worktree</p>
          )}
        </Panel>
        <Panel title="Candidate commit" stateRail="complete" actions={<FixtureBadge />}>
          {commitQ.data ? (
            <dl className="font-mono text-xs">
              <Row label="sha" value={commitQ.data.sha} />
              <Row label="parent" value={commitQ.data.parent_sha ?? "—"} />
              <Row label="files" value={String(commitQ.data.changed_files?.length ?? 0)} />
            </dl>
          ) : (
            <p className="text-xs text-[var(--muted)]">Not produced yet</p>
          )}
        </Panel>
        <Panel title="Runtime telemetry" stateRail="neutral" actions={<FixtureBadge />}>
          <p className="text-xs text-[var(--muted)]">
            Non-authoritative runtime_metadata (M-27): LangGraphRuntime / implementation alias from contract.
          </p>
          <Row label="model_alias" value={contractQ.data?.body.model_alias ?? "—"} />
        </Panel>
      </div>

      <Panel title="Action timeline" stateRail="running" actions={<FixtureBadge />}>
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="text-[var(--muted)]">
              <th className="p-1">tool</th>
              <th className="p-1">resource.action</th>
              <th className="p-1">status</th>
              <th className="p-1">policy</th>
            </tr>
          </thead>
          <tbody>
            {actionsQ.data?.map((a) => (
              <tr key={a.id} className="border-t border-[var(--border)]">
                <td className="p-1 font-mono">{a.tool}</td>
                <td className="p-1">
                  {a.resource}.{a.action}
                </td>
                <td className="p-1">
                  <StatusBadge value={a.status} />
                </td>
                <td className="p-1 font-mono text-[10px]">{a.policy_decision?.decision ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <Panel title="Retry lineage" stateRail="failed" actions={<FixtureBadge />}>
        <ul className="space-y-1 font-mono text-xs">
          {siblings.map((e) => (
            <li key={e.id}>
              {e.key} <StatusBadge value={e.status} kind="execution" /> attempt {e.attempt_number}
              {e.failure_class && <span className="text-rose-300"> — {e.failure_class}</span>}
            </li>
          ))}
          {siblings.length === 0 && <li className="text-[var(--muted)]">No sibling attempts</li>}
        </ul>
      </Panel>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2 py-0.5">
      <dt className="text-[var(--muted)]">{label}</dt>
      <dd className="truncate">{value}</dd>
    </div>
  );
}
