"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import * as Tabs from "@radix-ui/react-tabs";
import { ContractView } from "@/components/dag/ContractView";
import { EligibilityExplain } from "@/components/dag/EligibilityExplain";
import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { StatusBadge } from "@/components/status/StatusBadge";
import { getServices } from "@/lib/api/services";
import { qk } from "@/lib/query/keys";
import type { Task } from "@/lib/contracts/entity-types";

const TAB_IDS = [
  "overview",
  "contract",
  "dependencies",
  "specs",
  "acceptance",
  "executions",
  "artifacts",
  "commits",
  "evidence",
  "findings",
  "events",
] as const;

export function TaskInspector({
  task,
  projectId,
  cycleId,
  tab,
  onTabChange,
}: {
  task: Task;
  projectId: string;
  cycleId: string;
  tab: string;
  onTabChange: (tab: string) => void;
}) {
  const contractQ = useQuery({
    queryKey: ["contract", task.id],
    queryFn: async () => (await getServices()).tasks.contract(task.id),
  });
  const eligQ = useQuery({
    queryKey: ["eligibility", task.id],
    queryFn: async () => (await getServices()).tasks.eligibility(task.id),
  });
  const execQ = useQuery({
    queryKey: [...qk.task(task.id), "executions"],
    queryFn: async () => (await getServices()).executions.listByTask(task.id),
  });
  const dagQ = useQuery({
    queryKey: qk.taskDag(cycleId),
    queryFn: async () => (await getServices()).tasks.dag(cycleId),
  });
  const deps = dagQ.data?.edges.filter((e) => e.task_id === task.id) ?? [];
  const eventsQ = useQuery({
    queryKey: qk.cycleEvents(cycleId),
    queryFn: async () => (await getServices()).deliveryCycles.events(cycleId),
  });
  const taskEvents =
    eventsQ.data?.items.filter((e) => e.aggregate_id === task.id || e.payload?.task_id === task.id) ??
    [];

  const activeTab = TAB_IDS.includes(tab as (typeof TAB_IDS)[number]) ? tab : "overview";

  return (
    <aside className="fixed inset-y-0 right-0 z-40 w-full max-w-md overflow-y-auto border-l border-[var(--border)] bg-[var(--surface)] p-4 shadow-xl">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h2 className="font-mono text-lg text-amber-300">{task.key}</h2>
          <StatusBadge value={task.status} kind="task" />
        </div>
        <FixtureBadge />
      </div>
      <Tabs.Root value={activeTab} onValueChange={onTabChange}>
        <Tabs.List className="mb-3 flex flex-wrap gap-1">
          {TAB_IDS.map((t) => (
            <Tabs.Trigger
              key={t}
              value={t}
              className="rounded border border-[var(--border)] px-2 py-0.5 text-[10px] uppercase data-[state=active]:border-amber-500"
            >
              {t}
            </Tabs.Trigger>
          ))}
        </Tabs.List>
        <Tabs.Content value="overview">
          <Panel title="Overview" stateRail="neutral">
            <p className="text-sm">{task.title}</p>
            <p className="mt-2 text-xs text-[var(--muted)]">{task.work_type} · {task.origin}</p>
            {task.blocked_reason && (
              <p className="mt-2 text-xs text-orange-300">{task.blocked_reason}</p>
            )}
          </Panel>
          {eligQ.data && (
            <div className="mt-3">
              <EligibilityExplain eligible={eligQ.data.eligible} reasons={eligQ.data.reasons} />
            </div>
          )}
        </Tabs.Content>
        <Tabs.Content value="contract">
          {contractQ.data && <ContractView contract={contractQ.data} />}
        </Tabs.Content>
        <Tabs.Content value="dependencies">
          <Panel title="Dependencies" stateRail="neutral" actions={<FixtureBadge />}>
            <ul className="font-mono text-xs">
              {deps.map((d) => (
                <li key={d.depends_on_task_id}>{d.kind} → {d.depends_on_task_id.slice(0, 8)}</li>
              ))}
            </ul>
          </Panel>
        </Tabs.Content>
        <Tabs.Content value="executions">
          <Panel title="Executions" stateRail="running" actions={<FixtureBadge />}>
            <ul className="space-y-2">
              {execQ.data?.map((e) => (
                <li key={e.id}>
                  <Link href={`/executions/${e.id}`} className="font-mono text-sky-300 hover:underline">
                    {e.key}
                  </Link>{" "}
                  <StatusBadge value={e.status} kind="execution" />
                </li>
              ))}
            </ul>
          </Panel>
        </Tabs.Content>
        <Tabs.Content value="events">
          <Panel title="Events" stateRail="neutral" actions={<FixtureBadge />}>
            <ul className="max-h-64 space-y-1 overflow-y-auto font-mono text-[10px]">
              {taskEvents.map((e) => (
                <li key={e.id}>
                  #{e.sequence} {e.event_type}
                </li>
              ))}
            </ul>
          </Panel>
        </Tabs.Content>
        {(["specs", "acceptance", "artifacts", "commits", "evidence", "findings"] as const).map(
          (placeholder) => (
            <Tabs.Content key={placeholder} value={placeholder}>
              <Panel title={placeholder} stateRail="neutral" actions={<FixtureBadge />}>
                <p className="text-xs text-[var(--muted)]">
                  Linked {placeholder} for this task — compose via planning / assurance services when scoped.
                </p>
                <Link
                  href={`/projects/${projectId}/assurance?cycle=${cycleId}`}
                  className="text-amber-400 underline"
                >
                  Assurance workspace
                </Link>
              </Panel>
            </Tabs.Content>
          ),
        )}
      </Tabs.Root>
    </aside>
  );
}
