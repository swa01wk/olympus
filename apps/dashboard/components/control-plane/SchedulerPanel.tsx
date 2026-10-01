import Link from "next/link";
import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import type { Task } from "@/lib/contracts/entity-types";
import { ReasonCode } from "@/components/control-plane/ReasonCode";

export function SchedulerPanel({
  projectId,
  cycleId,
  tasks,
  scheduler,
}: {
  projectId: string;
  cycleId: string;
  tasks: Task[];
  scheduler: Record<string, unknown>;
}) {
  const blocked = tasks.filter((t) => t.status === "BLOCKED");
  const ready = tasks.filter((t) => t.status === "READY" || t.status === "RUNNING");
  const queued = Number(scheduler.queued_tasks ?? 0);

  return (
    <Panel title="Scheduler" stateRail={blocked.length ? "blocked" : "running"} actions={<FixtureBadge />}>
      <p className="mb-2 text-xs text-[var(--muted)]">Queued (server): {queued}</p>
      <div className="grid gap-3 md:grid-cols-2">
        <div>
          <h3 className="mb-1 text-[10px] font-semibold uppercase text-[var(--muted)]">Blocked</h3>
          <ul className="space-y-2">
            {blocked.map((t) => (
              <li key={t.id} className="rounded border border-[var(--border)] p-2">
                <Link
                  href={`/projects/${projectId}/cycles/${cycleId}/tasks?task=${t.id}&tab=overview&cycle=${cycleId}`}
                  className="font-mono text-amber-300 hover:underline"
                >
                  {t.key}
                </Link>
                {t.blocked_reason && <ReasonCode code={t.blocked_reason} />}
              </li>
            ))}
            {blocked.length === 0 && <p className="text-xs text-[var(--muted)]">None</p>}
          </ul>
        </div>
        <div>
          <h3 className="mb-1 text-[10px] font-semibold uppercase text-[var(--muted)]">Ready / Running</h3>
          <ul className="space-y-1 font-mono text-xs">
            {ready.map((t) => (
              <li key={t.id}>{t.key}</li>
            ))}
          </ul>
        </div>
      </div>
    </Panel>
  );
}
