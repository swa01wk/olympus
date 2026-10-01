import Link from "next/link";
import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { StatusBadge } from "@/components/status/StatusBadge";
import { EligibilityVerdict } from "@/components/release/EligibilityVerdict";
import type { Execution, ReleaseEligibilityEvaluation, Task } from "@/lib/contracts/entity-types";
import { isExecutionActive } from "@/lib/utils/execution-active";

export function StatusTiles({
  projectId,
  cycleId,
  tasks,
  executions,
  inboxCount,
  eligibility,
  blockedCount,
}: {
  projectId: string;
  cycleId: string;
  tasks: Task[];
  executions: Execution[];
  inboxCount: number;
  eligibility: ReleaseEligibilityEvaluation | null;
  blockedCount: number;
}) {
  const runningTasks = tasks.filter((t) => t.status === "RUNNING" || t.status === "READY");
  const activeExec = executions.filter((e) => isExecutionActive(e.status));
  const blocked = tasks.filter((t) => t.status === "BLOCKED");

  return (
    <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
      <Panel title="Active Tasks" stateRail="running" actions={<FixtureBadge />}>
        {runningTasks.map((t) => (
          <Link
            key={t.id}
            href={`/projects/${projectId}/cycles/${cycleId}/tasks?task=${t.id}&cycle=${cycleId}`}
            className="flex gap-2 font-mono text-xs hover:underline"
          >
            {t.key} <StatusBadge value={t.status} kind="task" />
          </Link>
        ))}
      </Panel>
      <Panel title="Running Executions" stateRail="running" actions={<FixtureBadge />}>
        {activeExec.map((e) => (
          <Link key={e.id} href={`/executions/${e.id}`} className="block font-mono text-xs text-sky-300 hover:underline">
            {e.key} — {e.agent_profile}
          </Link>
        ))}
      </Panel>
      <Panel title="Blocked Tasks" stateRail={blocked.length ? "blocked" : "neutral"} actions={<FixtureBadge />}>
        <p className="mb-1 text-[10px] text-[var(--muted)]">Server blocked count: {blockedCount}</p>
        {blocked.map((t) => (
          <div key={t.id} className="text-xs text-orange-300">
            {t.key}: {t.blocked_reason}
          </div>
        ))}
      </Panel>
      <Panel title="Human Attention" stateRail={inboxCount ? "waiting" : "neutral"} actions={<FixtureBadge />}>
        <span className="text-2xl font-semibold">{inboxCount}</span>
        <Link href={`/inbox?project=${projectId}`} className="ml-2 text-amber-400 underline">
          Open inbox
        </Link>
      </Panel>
      <Panel title="Tasks (deep)" stateRail="neutral" actions={<FixtureBadge />}>
        <Link href={`/projects/${projectId}/cycles/${cycleId}/tasks?cycle=${cycleId}`} className="text-amber-400 underline">
          Task DAG
        </Link>
      </Panel>
      <Panel title="Executions" stateRail="neutral" actions={<FixtureBadge />}>
        <Link href={`/projects/${projectId}/executions?cycle=${cycleId}`} className="text-amber-400 underline">
          Execution list
        </Link>
      </Panel>
      <Panel title="Agents" stateRail="neutral" actions={<FixtureBadge />}>
        <Link href={`/projects/${projectId}/agents?cycle=${cycleId}`} className="text-amber-400 underline">
          Agent ops
        </Link>
      </Panel>
      {eligibility && (
        <Panel title="Release Eligibility" stateRail="blocked" className="md:col-span-2" actions={<FixtureBadge />}>
          <EligibilityVerdict evaluation={eligibility} />
        </Panel>
      )}
    </div>
  );
}
